import subprocess
import threading

from addict import Dict

from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig
from pcvs.helpers.test import Test
from pcvs.orchestration.publishers import Publisher


class SetBuilder:
    def __init__(self, wrap=False):
        self._is_wrapper = wrap

    def collect_jobs(self):
        pass

    def generate_set(self):
        pass
    

class SerialBuilder(SetBuilder):
    def __init__(self):
        super().__init__(self)


class Manager:
    def __init__(self, max_size=0, builder=SerialBuilder()):
        self._dims = dict()
        self._builder = builder
        self._max_size = max_size
        self._count = Dict({
            "total": 0,
            "executed": 0
        })
    
    @property
    def executed_job(self):
        return self._count.executed

    @property
    def total_job(self):
        return self._count.total
    def add_job(self, job):
        value = min(self._max_size, job.get_dim())
        
        if self._max_size < value:
            self._max_size = value

        if value not in self._dims:
            self._dims.setdefault(value, list())

        self._dims[value].append(job)
        self._count.total += 1
        
    
    def get_leftjob_count(self):
        return self._count.total - self._count.executed

    def create_subset(self, max_dim):
        # in this function should take place a scheduling policy
        # for instance, gathering multiple tests, and modifying
        # the set to re-run PCVS as the task command
        if max_dim <= 0:
            return None
        
        the_set = None
        for k in sorted(self._dims.keys(), reverse=True):
            if len(self._dims[k]) <= 0:
                continue
            else:
                #assert(self._builder.job_grabber)
                job = self._dims[k].pop()
                if the_set is None:
                    the_set = Set([job])
                else:
                    the_set.add(job)
        return the_set

    def merge_subset(self, set):
        final = list()
        for job in set.content:
            if job.been_executed():
                job.save_final_result()
                self._count.executed += 1
                final.append(job)
            else:
                self.add_job(job)

        return final


class Set(threading.Thread):
    global_increment = 0

    def __init__(self, l=list()):
        assert(isinstance(l, list))
        self._id = self.global_increment
        self.global_increment += 1
        self._size = len(l)
        self._jobs = l
        self._completed = False
        self._is_wrapped = False
        super().__init__()
    
    def enable_wrapping(self, wrap_cli):
        self._wrap_cmd = wrap_cli
        self._is_wrapped = True
        
    def add(self, l):
        if not isinstance(l, list):
            l = [l]

        for job in l:
            assert(isinstance(job, Test))
            self._jobs.append(l)

    def __del__(self):
        pass

    def been_completed(self):
        return self._completed
    
    @property
    def size(self):
        return self._size

    @property
    def id(self):
        return self._id

    @property
    def dim(self):
        if self._size <= 0:
            return 0
        elif self._size == 1:
            return self._jobs[0].get_dim()
        else:
            return max(self._jobs, key=lambda x: x.get_dim())

    @property
    def content(self):
        for j in self._jobs:
            yield j

    def run(self):
        for job in self._jobs:
            p = subprocess.Popen('{}'.format(job.command),
                                 shell=True,
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE)
            job.executed()
            print("{}: {}".format(job.name, job.strstate))
        self._completed = True


class Orchestrator:
    def __init__(self):
        config_tree = MetaConfig.root
        self._conf = config_tree
        self._pending_sets = dict()
        self._sched_on = config_tree.validation.scheduling.sched_on
        self._max_res = config_tree.machine.nodes
        self._manager = Manager(self._max_res)
        self._maxconcurrent = config_tree.machine.concurrent_run
        self._publisher = Publisher(config_tree.validation.output)

    def __del__(self):
        pass

    #This func should only be a passthrough to the job manager
    def add_new_job(self, job):
        self._manager.add_job(job)

    def start_run(self, restart=False):
        nb_nodes = self._max_res
        last_count = 0
        #While some jobs are available to run
        while self._manager.get_leftjob_count() > 0 or len(self._pending_sets) > 0:
            # dummy init value
            new_set = not None
            while new_set is not None:
                # create a new set, if not possible, returns None
                new_set = self._manager.create_subset(nb_nodes)
                if new_set is not None:
                    # schedule the set asynchronously
                    nb_nodes -= new_set.dim
                    self._pending_sets[new_set.id] = new_set
                    new_set.run()

            # Now, look for a completion
            set = None
            for s in self._pending_sets.values():
                if s.been_completed():
                    set = s
                    break

            if set is not None:
                nb_nodes += set.dim
                del(self._pending_sets[set.id])
                flushable_tests = self._manager.merge_subset(set)

                for test in flushable_tests:
                    self._publisher.add_test_entry(test.to_json())
            else:
                pass
                #TODO: create backup to allow start/stop
            
            # Complex condition to trigger a dump of results
            # info result file at a periodic step of 5% of
            # the global workload
            if ((self._manager.executed_job - last_count) / self._manager.total_job) > 0.05:
                #TODO: Publish results periodically
                #1. on file system
                #2. directly into the selected bank
                self._publisher.finalize()
                last_count = self._manager.executed_job
        
        self._publisher.finalize()

    def pause_run(self):
        pass

    def run(self):
        #pre-actions done only once
        self.start_run(restart=False)
        pass