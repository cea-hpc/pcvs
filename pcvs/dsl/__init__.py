import json
import os
from enum import Enum, IntEnum
from typing import Dict, List

from pcvs import io
from pcvs.helpers import exceptions, git
from pcvs.testing.test import Test


class Job(Test):
    """Map a real job representation within a bank."""
    class Trend(IntEnum):
        REGRESSION = 0,
        PROGRESSION = 1,
        STABLE = 2

    def __init__(self, s=None) -> None:
        super().__init__()
        if isinstance(s, dict):
            self.from_json(s)

    def get_state(self) -> Test.State:
        """Retrieve job state as stored in the Run.

        :return: the state
        :rtype: Test.State
        """
        return self._state

    def load(self, s="") -> None:
        """Populate the job with given data.

        :param s: A Job's data dict representation
        :type s: dict
        """
        self.from_json(s)

    def dump(self) -> dict:
        """Return serialied job data.

        :return: the mapped representation
        :rtype: dict
        """
        return self.to_json()


class Run:
    """Depict a given run -> Git commit
    """

    def __init__(self, repo=None, cid=None, from_serie=None):
        """Create a new run.

        :param repo: the associated repo this run is coming from
        :type repo: Bank
        """
        # this attribute prevails
        if from_serie:
            repo = from_serie.repo

        self._repo = repo
        self._stage = {}
        self._cid = None

        if self._repo:
            self._cid = cid
            # self.load()

    def load(self, cid=None):
        if cid:
            self._cid = cid
        # load into _stage the actual content ?

    @property
    def changes(self):
        return self._stage

    @property
    def previous(self):
        l = self._repo.get_parents(self._cid)
        if l[0].get_info()['message'] == "INIT" or len(l) < 1:
            return None
        return Run(repo=self._repo, cid=l[0])

    @property
    def oneline(self):
        """TODO:
        """
        assert (isinstance(self._cid, git.Commit))
        d = self._cid.get_info()
        return "{}".format(d)

    @property
    def jobs(self):
        for file in self._repo.list_files(rev=self._cid):
            data = self._repo.get_tree(rev=self._cid, prefix=file)
            job = Job(json.loads(str(data)))
            yield job

    @property
    def get_full_data(self):
        root = [j.to_json() for j in self.jobs]
        return json.dumps(root)

    def get_data(self, jobname):
        res = Job()
        data = self._repo.get_tree(rev=self._cid, prefix=jobname)
        if not data:
            return data

        res.from_json(str(data))
        return res

    def update(self, prefix, data):
        if isinstance(data, Job):
            data = data.to_json()

        if isinstance(data, dict):
            data = json.dumps(data, default=lambda x: "Invalid type: {}".format(type(x)))

        self._stage[prefix] = data

    def update_flatdict(self, list_of_updates):
        for k, v in list_of_updates.items():
            self.update(k, v)

    def __handle_subtree(self, prefix, subdict):
        for k, v in subdict.items():
            if not isinstance(v, dict):
                self._stage[k] = v
            else:
                self.__handle_subtree("{}{}/".format(prefix, k), v)

    def update_treedict(self, list_of_updates):
        self.__handle_subtree("", list_of_updates)

    def get_info(self):
        return self._cid.get_info()

    def get_metadata(self):
        raw_msg = self._cid.get_info()['message']
        meta = raw_msg.split('\n')[2]
        return json.loads(meta)


class Serie:
    """TODO:
    """
    class Request(IntEnum):
        """TODO:
        """
        REGRESSIONS = 0
        RUNS = 1,

    """Depicts an history of runs for a given project/profile.
    """

    def __init__(self, branch):
        """TODO:
        """
        self._hdl = branch
        self._repo = branch.repo

    @property
    def repo(self):
        return self._repo

    @property
    def name(self):
        return self._hdl.name

    @property
    def last(self):
        """Return the last run for this serie.
        """
        return Run(self._repo, self._repo.revparse(self._hdl))

    def __len__(self):
        return len(self.find(self.Request.RUNS))

    def __str__(self):
        res = ""
        for run in self._repo.iterate_over(self._hdl):
            res += "* {}\n".format(Run(repo=self._repo, cid=run).oneline)
        return res

    def history(self):
        res = []

        parent = self.last
        while parent:
            res.append(parent)
            parent = parent.previous

        return res

    def find(self, op: Request, since=None, until=None, tree=None):
        """TODO:
        """
        res = None

        if op == self.Request.REGRESSIONS:
            job = Test()
            res = []
            for raw_job in self._repo.diff_tree(tree=tree, src=self._hdl,
                                                dst=None, since=since,
                                                until=until):
                job.from_json(raw_job)
                if job.state != Test.State.SUCCESS:
                    res.append(job)

        elif op == self.Request.RUNS:
            res = []
            for elt in self._repo.list_commits(rev=self._hdl, since=since, until=until):
                if elt.get_info()['message'] != "INIT":
                    res.append(Run(repo=self._repo, cid=elt))
        return res

    def commit(self, run, msg=None, metadata={}, timestamp=None):
        assert (isinstance(run, Run))
        root_tree = None
        msg = "New run" if not msg else msg
        try:
            raw_metadata = json.dumps(metadata)
        except:
            raw_metadata = ""

        commit_msg = """{}

{}""".format(msg, raw_metadata)

        for k, v in run.changes.items():
            root_tree = self._repo.insert_tree(k, v, root_tree)
        self._repo.commit(tree=root_tree, msg=commit_msg,
                          parent=self._hdl, timestamp=timestamp, orphan=False)
        # self._repo.gc()


class Bank:
    """
    Bank view from Python API
    """

    def __init__(self, path="", head=None):
        self._path = path
        self._repo = git.elect_handler(self._path)

        self._repo.open()
        if head:
            self._repo.set_head(head)
        else:
            first_branch = [
                b for b in self._repo.branches if b.name != "master"]
            if len(first_branch) <= 0:
                io.console.warn(
                    "This repository seems empty: {}".format(self._path))
            else:
                self._repo.set_head(first_branch[0].name)

        if not self._repo.get_branch_from_str('master'):
            t = self._repo.insert_tree(
                'README', "This file is intended to be used as a branch bootstrap.")
            c = self._repo.commit(t, "INIT", orphan=True)
            self._repo.set_branch(git.Branch(self._repo, 'master'), c)

    @property
    def path(self):
        return self._path

    def set_id(self, an, am, cn, cm):
        self._repo.set_identity(an, am, cn, cm)

    def connect(self):
        self._repo.open()

    def disconnect(self):
        if self._repo:
            self._repo.close()

    def new_serie(self, serie_name=None):
        hdl = self._repo.new_branch(serie_name)
        return Serie(hdl)

    def get_serie(self, serie_name=None):
        """TODO
        """
        if not serie_name:
            serie_name = self._repo.get_head().name

        branch = self._repo.get_branch_from_str(serie_name)
    
        if not branch:
            return None

        return Serie(branch)

    def list_series(self, project=None):
        """TODO:
        """
        res = []
        for elt in self._repo.branches:
            array = elt.name.split('/')
            if project is None or array[0].lower() == project.lower():
                res.append(Serie(elt))
        return res

    def list_all(self) -> Dict[str, List]:
        """TODO:
        """
        res = {}
        for project in self.list_projects():
            if project != "master":
                res[project] = self.list_series(project)
        return res

    def list_projects(self) -> List[str]:
        """Given the bank, list projects with at least one run.

        In a bank, each branch is a project, just list available branches.
        `master` branch is not a valid project.

        :return: A list of available projects
        :rtype: list of str
        """
        projects = [elt.name.split('/')[0] for elt in self._repo.branches if elt.name != "master"]
        return list(set(projects))
