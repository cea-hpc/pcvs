from enum import Enum, IntEnum
import os
from typing import List
from pcvs.testing.test import Test
from pcvs.backend import bank
from pcvs.helpers import git, exceptions
import json


class Job(Test):
    """Map a real job representation within a bank."""
    
    def __init__(self, s=None):
        super().__init__()
        if isinstance(s, dict):
            self.from_json(s)
    
    def get_state(self):
        return self._state
    
    def get_date(self):
        return None
    
    def load(self, s=""):
        self.from_json(s)

    def dump(self):
        return self.to_json()


class Run:
    """Depict a given run -> Git commit
    """
    def __init__(self, repo, commit):
        """TODO:
        """
        assert(repo.is_open())
        self._repo = repo
        self._id = commit
    
    @property
    def oneline(self):
        """TODO:
        """
        d = self._repo.get_info(self._id)
        return "{} ({} <{}>)".format(d['date'], d['author'], d['authmail'])
    
    @property
    def tests(self):
        res = {}
        for file in self._repo.list_files(rev=self._id, prefix=None):
            data = self._repo.get_blob(rev=self._id, prefix=file)
            job = Job(json.loads(data))
            res[job.name] = job
        return res

    def get_data(self, jobname):
        res = Job()
        res.from_json(self._repo.get_blob(rev=self._id, prefix=jobname))
        return res
        
    def __str__(self):
        d = self._repo.get_info(self._id)
        return """Date: {date}
Author: {auth} <{mail}>
Infos: {tests}""".format(date=d['date'], auth=d['author'], mail=d['authmail'],
                          tests="\n\t- ".join(d['metadata']))
        
class Serie:
    
    class Finder(IntEnum):
        """TODO:
        """
        REGRESSIONS = 0
        RUNS = 1,
        
    
    """Depicts an history of runs for a given project/profile.
    """
    def __init__(self, repo, name):
        """TODO:
        """
        assert(repo.is_open())
        self._repo = repo
        self._id = name
        self._root = self._repo.branches[name]
    
    @property
    def last(self):
        """Return the last run for this serie.
        """
        return Run(self._repo, self._root.peel().short_id)

    def __str__(self):
        res = ""
        for run in self._repo.iterate_over(self._repo.revparse(self._root)):
            res += "* {}\n".format(Run(self._repo, run).oneline)
        return res
    
    def get(self, op: Finder, since=None, until=None, tree=None):
        res = None
        
        if op == self.Finder.REGRESSIONS:
            job = Test()
            res = []
            for raw_job in self._repo.diff_tree(tree=tree, src=self._root,
                                                dst=None, since=since,
                                                until=until):
                job.from_json(raw_job)
                if job.state != Test.State.SUCCESS:
                    res.append(job)
                    
        elif op == self.Finder.RUNS:
            res = []
            for run_id in self._repo.list_commits(rev=self._root, since=since, until=until):
                res.append(Run(self._repo, run_id))
        return res
    
    def set(self, batch):
        raise NotImplementedError()

    def commit(self):
        raise NotImplementedError()
        oid = self._repo.commit(self._id)
        self._root = oid
    

class Bank(bank.Bank):
    """
    Bank view from Python API
    """
    def __init__(self, path="", name=""):
        super().__init__(path, name)
        self.connect_repository()
    
    def load_serie(self, serie_name=None):
        """TODO
        """
        if not serie_name:
            serie_name = self._proj_name
            
        if serie_name not in self._repo.branches:
            raise exceptions.BankException.ProjectNameError(serie_name)
        
        return Serie(self._repo, serie_name)
        
        
    def save_serie(self, serie_name, serie: Serie):
        """TODO:
        """
        if serie_name not in self._repo.branches:
            raise exceptions.BankException.ProjectNameError(serie_name)
        




class JobTrend:
    # States from Test package are reused here.
    class State(IntEnum):
        TREND_REGRESS = 0,
        TREND_PROGRESS = 1,
        TREND_STABLE =  2,
    
    def __init__(self):
        pass


class JobTree:
    """
    Map a intermediate node in the whole test-suite subtree.
    """

    def __init__(self):
        self.__subtrees: List[JobTree] = []
        self.__jobs: List[Job] = []
        
    def find_differences(self, other_tree):
        """Extract jobs having different status from one tree to another.
        
        :param[in] other_tree: the other tree to look for jobs
        :type other_tree: JobTree
        
        :returns: a dict, mapping jobs and reasons of divergence
        :rtype: dict"""
        return []
    
    def find_regressions(self, time_limit=-1):
        """Identify jobs newly failing while being successful until now."""
        return []
    
    def find_subtree(self, prefix):
        return JobTree()
    
    def extract(self, func, revision=None):
        return None

    def trend(self, date_start=None, date_end=None):
        return JobTrend()
    
    def intersect(self, other_tree):
        return JobTree()
    
    def add(self, other_tree):
        pass

    def sub(self, other_tree):
        """
        """
        pass

    def xor(self, other_tree):
        """
        """
        pass
    
    def rewind(self, prev_date):
        """
        """
        pass

    def commit(self):
        """
        """
        pass
    
        
bank.init()
