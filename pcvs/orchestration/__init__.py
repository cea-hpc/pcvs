import subprocess
import threading
import time

from addict import Dict

from pcvs.helpers import log
from pcvs.helpers.exceptions import OrchestratorException
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.publishers import Publisher
from pcvs.testing.test import Test
from pcvs.backend import session

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
    job_hashes = dict()
    
    def __init__(self, max_size=0, builder=SerialBuilder(), publisher=None):
        self._dims = dict()
        self._builder = builder
        self._max_size = max_size
        self._publisher = publisher
        self._count = Dict({
            "total": 0,
            "executed": 0
        })
    

    def add_job(self, job):
        value = min(self._max_size, job.get_dim())
        
        if self._max_size < value:
            self._max_size = value

        if value not in self._dims:
            self._dims.setdefault(value, list())

        self._dims[value].append(job)
        self.job_hashes[hash(job.name)] = job
        self._count.total += 1
        
    def get_count(self, tag=None):
        if tag is None:
            tag = 'total'
        assert(tag in self._count.keys())
        return self._count[tag]
        
    def resolve_deps(self):
        for joblist in self._dims.values():
            for job in joblist:
                self.resolve_single_job_deps(job, list())
    
    def resolve_single_job_deps(self, job, chain):
        
        chain.append(job.name)
        
        for depname, depobj in job.deps.items():
            if depobj is None:
                hashed_dep = hash(depname)
                if hashed_dep not in self.job_hashes:
                    raise OrchestratorException.UndefDependencyError(depname)
                
                job_dep = self.job_hashes[hashed_dep]
                
                if job_dep.name in chain:
                    raise OrchestratorException.CircularDependencyError(job_dep.name)    
                
                self.resolve_single_job_deps(job_dep, chain)
                job.set_dep(depname, job_dep)
    
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
                job: Test = self._dims[k].pop()
                
                if job:
                    if job.been_executed() or job.has_failed_dep():
                        if job.has_failed_dep():
                            job.save_final_result(rc=-1, time=0.0, out=Test.NOSTART_STR)
                            job.display()
                        
                        self._count.executed += 1
                        self._publisher.add(job.to_json())
                        # sad to break, should retry
                        break
                    elif not job.is_pickable():
                        self._dims[k].append(job)
                        
                        # careful: it means jobs are picked up
                        # but not popped from 
                        while job and not job.is_pickable():
                            job = job.first_valid_dep()
                    
                if job:
                    job.picked()
                    the_set = Set()
                    the_set.add(job)
                    break
                    
        return the_set

    def merge_subset(self, set):
        final = list()
        for job in set.content:
            if job.been_executed():
                self._count.executed += 1
                self._publisher.add(job.to_json())
            else:
                self.add_job(job)


class Set(threading.Thread):
    global_increment = 0
    
    def __init__(self):
        self._id = Set.global_increment
        Set.global_increment += 1
        self._size = 0
        self._jobs = list()
        self._completed = False
        self._is_wrapped = False
        super().__init__()
    
    def enable_wrapping(self, wrap_cli):
        self._wrap_cmd = wrap_cli
        self._is_wrapped = True
        
    def add(self, l):
        if not isinstance(l, list):
            l = [l]
        self._jobs += l
        self._size = len(self._jobs)

    def __del__(self):
        pass
    
    def is_empty(self):
        return len(self._jobs) == 0

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
            try:
                p = subprocess.Popen('{}'.format(job.wrapped_command),
                                 shell=True,
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE)
                start = time.time()
                stdout, _ = p.communicate(timeout=job.timeout)
                final = time.time() - start
                rc = p.returncode
                
            except subprocess.TimeoutExpired:
                p.kill()
                final = job.timeout
                stdout, _ = p.communicate()
                rc = Test.Timeout_RC  #nah, to be changed
            except:
                raise
            job.save_final_result(time=final, rc=rc, out=stdout)
            job.display()

        self._completed = True


class Orchestrator:
    def __init__(self):
        config_tree = MetaConfig.root
        self._conf = config_tree
        self._pending_sets = dict()
        self._max_res = config_tree.machine.nodes
        self._publisher = Publisher(config_tree.validation.output)
        self._manager = Manager(self._max_res, publisher=self._publisher)
        self._maxconcurrent = config_tree.machine.concurrent_run
        
        
    def __del__(self):
        pass

    def print_infos(self):
        log.manager.print_item("Total base: {} test(s)".format(self._manager.get_count('total')))
        log.manager.print_item("Concurrent launches: {} job(s)".format(self._maxconcurrent))
        log.manager.print_item("Number of resources: {}".format(self._max_res))
        
    #This func should only be a passthrough to the job manager
    def add_new_job(self, job):
        self._manager.add_job(job)

    def start_run(self, the_session=None, restart=False):
        self._manager.resolve_deps()
        self.print_infos()
        nb_nodes = self._max_res
        last_progress = 0
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
                self._manager.merge_subset(set)
            else:
                pass
                #TODO: create backup to allow start/stop
            
            current_progress = self._manager.get_count('executed') / self._manager.get_count('total')
                
            # Condition to trigger a dump of results
            # info result file at a periodic step of 5% of
            # the global workload
            if (current_progress - last_progress) > 0.05:
                #TODO: Publish results periodically
                #1. on file system
                #2. directly into the selected bank
                self._publisher.flush()
                last_progress = current_progress
                if the_session is not None:
                    session.update_session_from_file(the_session.id, {'progress': current_progress * 100})
                
        
        self._publisher.flush()

    def pause_run(self):
        pass

    def run(self, session):
        #pre-actions done only once
        self.start_run(session, restart=False)
        pass