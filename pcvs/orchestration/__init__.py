from pcvs.helpers.test import Test
from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.publishers import Publisher
from addict import Dict


class Set:
    _completed = list()

    def __init__(self, l):
        assert(isinstance(l, list))
        self._size = len(l)
        self._jobs = l
    
    def __del__(self):
        pass

    @classmethod
    def remaining_to_complete(cls):
        return len(cls._completed) > 0

    @classmethod
    def wait_for_completion(cls):
        if len(cls._completed) == 0:
            return None
        return cls._completed.pop()
    
    @property
    def size(self):
        return self._size

    @property
    def dim(self):
        #TODO: fix
        return 1
    
    @property
    def content(self):
        for j in self._jobs:
            yield j

    def start(self):
        log.warn("start the set()")
        import time
        time.sleep(2)
        self._completed.append(self)

class Orchestrator:
    def __init__(self):
        config_tree = MetaConfig.root
        self._conf = config_tree
        self._pool = list()
        self._sched_on = config_tree.validation.scheduling.sched_on
        self._size = config_tree.machine.nodes
        # +1 because, self._size is also a valid range value
        # 0 is a bit useless though
        self._dims = [list() for d in range(0, self._size+1)]
        self._count = Dict({
            "total": 0,
            "executed": 0
        })
        self._maxconcurrent = config_tree.machine.concurrent_run
        self._publisher = Publisher(config_tree.validation.output)

    def __del__(self):
        pass

    def add_new_job(self, job):
        value = min(self._size, job.get_dim(self._sched_on))
        if not isinstance(self._dims[value], list):
            self._dims[value] = list()
        self._dims[value].append(job)
        self._count.total += 1

    def get_leftjob_count(self):
        print(self._count.total, self._count.executed)
        return self._count.total - self._count.executed

    def build_set(self, max_dim):
        #in this function should take place a scheduling policy
        #for instance, gathering multiple tests, and modifying
        #the set to re-run PCVS as the task command
        if max_dim <= 0:
            return None

        for ent in self._dims[::-1]:
            if len(ent) <= 0:
                continue
            else:
                return Set([ent.pop()])
        return None
    
    def destroy_set(self, set):
        self._count.executed += set.size
        for job in set.content:
            job.save_final_result()
            self._publisher.add_test_entry(job.to_json())

    
    def start_run(self, restart=False):
        nb_nodes = self._size
        last_count = 0
        #While some jobs are available to run
        while self.get_leftjob_count() > 0 or Set.remaining_to_complete():
            print("left: {} / remain_set: {}".format(self.get_leftjob_count(), Set.remaining_to_complete()))
            # dummy init value
            new_set = not None
            while new_set is not None:
                # create a new set, if not possible, returns None
                new_set = self.build_set(nb_nodes)
                if new_set is not None:
                    # schedule the set asynchronously
                    nb_nodes -= new_set.dim
                    new_set.start()

            # Now, look for a completion
            set = Set.wait_for_completion()
            if set is not None:
                nb_nodes += set.dim
                self.destroy_set(set)
            else:
                pass
                #TODO: create backup to allow start/stop
            
            # Complex condition to trigger a dump of results
            # info result file at a periodic step of 5% of
            # the global workload
            if ((self._count.executed - last_count) / self._count.total) > 0.05:
                #TODO: Publish results periodically
                #1. on file system
                #2. directly into the selected bank
                self._publisher.finalize()
                last_count = self._count.executed
        
        self._publisher.finalize()

    def pause_run(self):
        pass

    def run(self):
        #pre-actions done only once
        self.start_run(restart=False)
        pass