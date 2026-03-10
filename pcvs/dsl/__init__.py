from __future__ import annotations

import json
import sys
from datetime import datetime
from enum import IntEnum
from typing import Any
from typing import Iterable

from typing_extensions import Self

from pcvs import io
from pcvs.helpers import git
from pcvs.testing.test import Test
from pcvs.testing.teststate import TestState


class Job(Test):
    """Map a real job representation within a bank."""

    class Trend(IntEnum):
        REGRESSION = 0
        PROGRESSION = 1
        STABLE = 2

    def __init__(
        self, json_content: dict[str, Any] | None = None, filepath: str | None = None
    ) -> None:
        """
        Init a Job object from json.

        :param json_content: the content of the test.
        :param filepath: optinnal, where does the above json comme from,
            this will be used in error messages given to the user if the test json is not valid.
        """
        super().__init__()
        if json_content is not None:
            assert filepath is not None
            self.from_json(json_content, filepath)

    def load(self, test_json: dict[str, Any], filepath: str) -> None:
        """
        Populate the job with given data.

        :param test_json: A Job's data dict representation
        :param filepath: optinnal, path of the json source, same as for init.
        """
        self.from_json(test_json, filepath)

    def dump(self) -> dict[str, Any]:
        """
        Return serialied job data.

        :return: the mapped representation
        """
        return self.to_json()


class Run:
    """Depict a given run -> Git commit"""

    # TODO modify comportement to avoid recursive definition
    def __init__(
        self,
        repo: git.GitByGeneric | None = None,
        cid: git.Commit | None = None,
        from_series: Series | None = None,
    ):
        """
        Create a new run.

        :param repo: the associated repo this run is coming from
        :param cid: optinnal, git commit object to select that represent the selected run in the series.
        :param from_series: initialise the underlying repo of the run from the Series object,
            override the repo parameter.
        """
        # this attribute prevails
        if isinstance(from_series, Series):
            repo = from_series.repo

        self._repo = repo
        self._cid = None
        self._stage: dict = {}

        if self._repo is not None:
            if isinstance(cid, git.Commit):
                self._cid = cid
            # self.load()

    def load(self, cid: git.Commit) -> None:
        """
        Set the run to represent the given commit.

        :param cid: git commit
        """
        self._cid = cid

    @property
    def changes(self) -> dict:
        return self._stage

    @property
    def previous(self) -> Self | None:
        """
        Get the previous run from the Series (the first commit of the branch),
            or None of the is the first run of the Series.

        :return: The previous run in the current series.
        """
        assert self._repo is not None and self._cid is not None
        runs = self._repo.get_parents(self._cid)
        if len(runs) <= 0 or runs[0].get_info()["message"] == "INIT":
            return None
        return Run(repo=self._repo, cid=runs[0])  # type: ignore

    @property
    def oneline(self) -> str:
        """Get commit metadata."""
        assert isinstance(self._cid, git.Commit)
        d = self._cid.get_info()
        return "{}".format(d)

    @property
    def jobs(self) -> Iterable[Job]:
        """Iterate over jobs present in the Run."""
        assert self._repo is not None
        for file in self._repo.list_files(rev=self._cid):
            if file in ["README", ".pcvs-cache/conf.json"]:
                continue
            io.console.nodebug(f"Reading: {file}")
            data = self._repo.get_tree(tree=self._cid, prefix=file)
            job = Job(json.loads(str(data)), file)
            yield job

    @property
    def get_full_data(self) -> str:
        """Get a list of the json of all the runs."""
        root = [j.to_json() for j in self.jobs]
        return json.dumps(root)

    def get_data(self, jobname: str) -> Job | None:
        """
        Get the job object corresponding to jobname.

        :param jobname: the name of the job to retrieve from the run.
        :return: The job if found.
        """
        res = Job()
        assert self._repo is not None
        data = self._repo.get_tree(tree=self._cid, prefix=jobname)
        if isinstance(data, git.Blob):
            res.from_json(
                json.loads(str(data)), f"Validation from bank {self._cid} for job {jobname}"
            )
            return res
        return None

    def update(self, prefix: str, data: Job | dict[str, Any] | str) -> None:
        """
        Update the data of a Job/Test.

        :param prefix: Job name in git, most likely job.name.
        :param data: a Job object or a dict representing the json of a job/test to store.
        """
        if isinstance(data, Job):
            data = data.to_json()
        if isinstance(data, dict):
            data = json.dumps(data, default=lambda x: "Invalid type: {}".format(type(x)))
        assert isinstance(data, str)
        self._stage[prefix] = data

    def update_flatdict(self, updates: dict[str, Job | dict[str, Any] | str]) -> None:
        """
        Same as the update function, but for all the items in updates.

        :param updates: a list of Jobs to updates.
        """
        for k, v in updates.items():
            self.update(k, v)

    def __handle_subtree(self, prefix: str, subdict: dict[str, Any]) -> None:
        for k, v in subdict.items():
            if not isinstance(v, dict):
                self._stage[k] = v
            else:
                self.__handle_subtree(f"{prefix}{k}/", v)

    def update_treedict(self, updates: dict[str, Any]) -> None:
        self.__handle_subtree("", updates)

    def get_info(self) -> dict[str, Any]:
        """Get run commit Metadata."""
        assert self._cid is not None
        return self._cid.get_info()

    def get_metadata(self) -> dict[str, Any]:
        assert self._cid is not None
        raw_msg = self._cid.get_info()["message"]
        meta = raw_msg.split("\n")[2]
        json_dict = json.loads(meta)
        assert isinstance(json_dict, dict)
        return json_dict


class Series:
    """TODO:"""

    class Request(IntEnum):
        """TODO:"""

        REGRESSIONS = 0
        RUNS = 1

    # Depicts an history of runs for a given project/profile.

    def __init__(self, branch: git.Branch):
        """TODO:"""
        self._hdl: git.Branch = branch
        self._repo: git.GitByGeneric = branch.repo

    @property
    def repo(self) -> git.GitByGeneric:
        return self._repo

    @property
    def name(self) -> str:
        return self._hdl.name

    @property
    def last(self) -> Run:
        """Return the last run for this series."""
        return Run(self._repo, self._repo.revparse(self._hdl))

    def __len__(self) -> int:
        return len(self.find(self.Request.RUNS))

    def __str__(self) -> str:
        res = ""
        for run in self._repo.iterate_over(self._hdl):
            res += "* {}\n".format(Run(repo=self._repo, cid=run).oneline)
        return res

    def history(self, limit: int = sys.maxsize) -> list[Run]:
        res = []
        size = 0

        parent: Run | None = self.last
        while parent is not None and size < limit:
            res.append(parent)
            size += 1
            parent = parent.previous

        return res

    def find(  # type: ignore
        self,
        op,  # Request is not yet defined and sphinx does not support future annotation
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Job | Run]:
        """TODO:"""
        res: list[Job | Run] = []
        if op == self.Request.REGRESSIONS:
            # TODO: implement repo.diff_tree
            assert False  # repo.diff_tree is not implemented, do not use
            tree = None
            job = Job()
            for raw_job in self._repo.diff_tree(
                tree=tree, src=self._hdl, dst=None, since=since, until=until
            ):
                job.from_json(raw_job, None)
                if job.state != TestState.SUCCESS:
                    res.append(job)

        elif op == self.Request.RUNS:
            for elt in self._repo.list_commits(rev=self._hdl, since=since, until=until):
                if elt.get_info()["message"] != "INIT":
                    res.append(Run(repo=self._repo, cid=elt))
        return res

    def commit(
        self,
        run: Run,
        msg: str | None = None,
        metadata: dict | None = None,
        timestamp: int | None = None,
    ) -> None:
        if metadata is None:
            metadata = {}
        assert isinstance(run, Run)
        root_tree = None
        msg = "New run" if not msg else msg
        try:
            raw_metadata = json.dumps(metadata)
        except Exception:
            raw_metadata = ""

        commit_msg = f"{msg}\n\n{raw_metadata}"

        for k, v in run.changes.items():
            root_tree = self._repo.insert_tree(k, v, root_tree)
        assert root_tree is not None
        self._repo.do_commit(
            tree=root_tree, msg=commit_msg, parent=self._hdl, timestamp=timestamp, orphan=False
        )
        # self._repo.gc()


class Bank:
    """Bank view from Python API"""

    def __init__(self, path: str = "", head: str | None = None):
        self._path: str = path
        self._repo: git.GitByGeneric = git.elect_handler(self._path)

        self._repo.open()
        if head is not None:
            self._repo.set_head(head)
        else:
            first_branch = [b for b in self._repo.branches() if b.name != "master"]
            if len(first_branch) <= 0:
                io.console.warn("This repository seems empty: {}".format(self._path))
            else:
                self._repo.set_head(first_branch[0].name)

        if not self._repo.get_branch_from_str("master"):
            t = self._repo.insert_tree(
                "README", "This file is intended to be used as a branch bootstrap."
            )
            c = self._repo.do_commit(t, "INIT", orphan=True)
            self._repo.set_branch(git.Branch(self._repo, "master"), c)

    @property
    def path(self) -> str:
        return self._path

    def set_id(self, an: str, am: str, cn: str, cm: str) -> None:
        self._repo.set_identity(an, am, cn, cm)

    def connect(self) -> None:
        self._repo.open()

    def disconnect(self) -> None:
        # can happen is the object is destroy before the constructor is called ...
        if self._repo is not None:
            if self._repo.is_open():
                self._repo.close()

    def new_series(self, series_name: str) -> Series:
        assert series_name is not None
        hdl = self._repo.new_branch(series_name)
        return Series(hdl)

    def get_series(self, series_name: str | None = None) -> Series | None:
        """TODO"""
        if not series_name:
            series_name = self._repo.get_head().name

        branch = self._repo.get_branch_from_str(series_name)

        if not branch:
            return None

        return Series(branch)

    def list_series(self, project: str | None = None) -> list[Series]:
        """TODO:"""
        res: list[Series] = []
        for elt in self._repo.branches():
            array = elt.name.split("/")
            if project is None or array[0].lower() == project.lower():
                res.append(Series(elt))
        return res

    def list_all(self) -> dict[str, list]:
        """TODO:"""
        res = {}
        for project in self.list_projects():
            if project != "master":
                res[project] = self.list_series(project)
        return res

    def list_projects(self) -> list[str]:
        """Given the bank, list projects with at least one run.

        In a bank, each branch is a project, just list available branches.
        `master` branch is not a valid project.

        :return: A list of available projects
        """
        projects = []
        for elt in self._repo.branches():
            if elt.name != "master":
                projects.append(elt.name.split("/")[0])
        return list(set(projects))
