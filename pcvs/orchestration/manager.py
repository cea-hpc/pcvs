from pcvs.helpers import log
from pcvs.helpers.exceptions import OrchestratorException
from pcvs.helpers.system import MetaConfig, MetaDict
from pcvs.orchestration.set import Set
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


class Manager:
    """Gather and manipulate Jobs under a hiararchical architecture.

    A Manager is in charge of carrying jobs during the scheduling. Jobs are
    divided hierarchicaly (basically, depending on the number of resource
    requested to be run). To extract jobs to be scheduled, a Manager will create
    Set()s. Once completed Sets are merged to the Manager before publishing the
    results.

    :ivar dims: hierarchical dict storing jobs
    :type dims: dict
    :ivar _max_size: max number of resources allowed by the profile
    :type _max_size: int
    :ivar _publisher: the Formatter object, publishing results into files
    :type _publisher: :class:`ResultFileManager`
    :ivar _count: dict gathering various counters (total, executed...)
    :type _count: dict 
    """
    job_hashes = dict()
    dep_rules = dict()

    def __init__(self, max_size=0, builder=None, publisher=None):
        """constructor method.

        :param max_size: max number of resource allowed to schedule.
        :type max_size: int
        :param builder: Not used yet
        :type builder: None
        :param publisher: requested publisher by the orchestrator
        :type publisher: :class:`ResultFileManager`
        """
        self._comman = MetaConfig.root.get_internal('comman')
        self._plugin = MetaConfig.root.get_internal('pColl')
        self._concurrent_level = MetaConfig.root.machine.get('concurrent_run', 1)

        self._dims = dict()
        self._max_size = max_size
        self._publisher = publisher
        self._count = MetaDict({
            "total": 0,
            "executed": 0
        })

    def get_dim(self, dim):
        """Get the list of jobs satisfying the given dimension.

        :param dim: the target dim
        :type dim: int
        :return: the list of jobs for this dimension, empty if dim is invalid
        :rtype: list
        """
        if dim not in self._dims:
            return []
        return self._dims[dim]

    @property
    def nb_dims(self):
        """Get max number of defined dimensions.

        :return: the max dimension length
        :rtype: int
        """
        return self._max_size

    def add_job(self, job):
        """Store a new job to the Manager table.

        :param job: The job to append
        :type job: :class:`Test`
        """
        value = min(self._max_size, job.get_dim())

        if self._max_size < value:
            self._max_size = value

        if value not in self._dims:
            self._dims.setdefault(value, list())

        self._dims[value].append(job)

        hashed = job.jid
        # if test is not know yet, add + increment
        if hashed not in self.job_hashes:
            self.job_hashes[hashed] = job
            self._count.total += 1
            self.save_dependency_rule(job.basename, job)
            
    def save_dependency_rule(self, pattern, jobs):
        assert(isinstance(pattern, str))
        
        if not isinstance(jobs, list):
            jobs = [jobs]
            
        self.dep_rules.setdefault(pattern, list())
        self.dep_rules[pattern] += jobs
        
    def get_count(self, tag="total"):
        """Access to a particular counter.

        :param tag: a specific counter to target, defaults to "total"
        :type tag: str
        :return: a count
        :rtype: int
        """
        return self._count[tag] if tag in self._count else 0

    def resolve_deps(self):
        """Resolve the whole dependency graph.

        This function is meant to be called once and browse every single tests
        to resolve dep names to their real associated object.
        """
        for joblist in self._dims.values():
            for job in joblist:
                self.resolve_single_job_deps(job, list())

    def print_dep_graph(self, outfile=None):
        s = ["digraph D {"]
        for joblist in self._dims.values():
            for job in joblist:
                for d in job.get_dep_graph().keys():
                    s.append('"{}"->"{}";'.format(job.name, d))
        s.append("}")
        
        if not outfile:
            print("\n".join(s))
        else:
            with open(outfile, 'w') as fh:
                fh.write("\n".join(s))

    def resolve_single_job_deps(self, job, chain):
        """Resolve the dependency graph for a single test.

        The 'chain' argument contains list of "already-seen" dependency, helping
        to detect circular deps.

        :raises UndefDependencyError: a depname does not have a related object
        :raises CircularDependencyError: a circular dep is detected from this
            job.
        :param job: the job to resolve
        :type job: :class:`Test`
        :param chain: list of already-seen jobs during this walkthrough
        :type chain: list
        """
        chain.append(job.name)
        for depname in job.job_depnames:

            hashed_dep = Test.get_jid_from_name(depname)
            if hashed_dep in self.job_hashes:
                job_dep_list = [self.job_hashes[hashed_dep]]
            elif depname in self.dep_rules:
                job_dep_list = self.dep_rules[depname]
            else:
                raise OrchestratorException.UndefDependencyError(depname)

            for job_dep in job_dep_list:
                if job_dep.name in chain:
                    raise OrchestratorException.CircularDependencyError(chain)
                
                # without copying the chain, resolution of siblings deps will alter
                # the same list --> a single dep may appear multiple time and raise
                # a false CiprcularDep
                # solution: resolve subdep path in their own chain :)
                self.resolve_single_job_deps(job_dep, list(chain))
                job.resolve_a_dep(depname, job_dep)

    def get_leftjob_count(self):
        """Return the number of jobs remainig to be executed.

        :return: a number of jobs
        :rtype: int
        """
        return self._count.total - self._count.executed

    def publish_job(self, job, publish_args=None):
        if publish_args:
            job.save_final_result(**publish_args)

        if self._comman:
            self._comman.send(job)
        self._count.executed += 1
        self._count[job.state] += 1
        self._publisher.save(job)

    def prune_non_runnable_jobs(self):
        for k in sorted(self._dims.keys(), reverse=True):
                if len(self._dims[k]) <= 0:
                    continue
                else:
                    removed_jobs = list()
                    for job in self._dims[k]:
                        if job.pick_count() > Test.SCHED_MAX_ATTEMPTS:
                            self.publish_failed_to_run_job(job, Test.MAXATTEMPTS_STR, Test.State.ERR_OTHER)
                            removed_jobs.append(job)
                    for elt in removed_jobs:
                        self._dims[k].remove(elt)
            

            

    def create_subset(self, max_dim):
        """Extract one or more jobs, ready to be run.

        :param max_dim: maximum number of resource allowed by any picked job.
        :type max_dim: int
        :return: A set of jobs
        :rtype: :class:`Set`
        """
        # in this function should take place a scheduling policy
        # for instance, gathering multiple tests, and modifying
        # the set to re-run PCVS as the task command
        if max_dim <= 0:
            return None

        the_set = None
        self._plugin.invoke_plugins(Plugin.Step.SCHED_SET_BEFORE)
        user_sched_job = self._plugin.has_enabled_step(Plugin.Step.SCHED_JOB_EVAL)
        
        if self._plugin.has_enabled_step(Plugin.Step.SCHED_SET_EVAL):
            the_set = self._plugin.invoke_plugins(
                Plugin.Step.SCHED_SET_EVAL,
                jobman=self,
                max_dim=max_dim,
                max_job_limit=int(self._count.total / self._concurrent_level)
            )
        else:
            for k in sorted(self._dims.keys(), reverse=True):
                if len(self._dims[k]) <= 0 or max_dim < k:
                    continue
                else:
                    # assert(self._builder.job_grabber)
                    job: Test = self._dims[k].pop(0)
                    publish_job_args = {}
                    if job:
                        if job.been_executed() or job.state == Test.State.IN_PROGRESS:
                            # skip job (only a pop() to do)
                            continue

                        elif not job.has_completed_deps():

                            # take the first unresolved dep to be scheduled
                            # instead
                            # CAUTION: no schedulable dep may be found at
                            # present time. In the meantime, the completion may
                            # occurs concurrently
                            self._dims[k].append(job)
                            # pick up a dep
                            dep_job = job.first_incomplete_dep()
                            while dep_job and not dep_job.has_completed_deps():
                                dep_job = dep_job.first_incomplete_dep()
                            # no "incomplete" task has been found
                            # this may due to a dep completion in the mean time
                            # discard for now, wait for another process
                            # to schedule this job
                            if dep_job:
                                job = dep_job
                            else:
                                break

                        # from here, it can be the original job or one of its
                        # dep tree. But we are sure this job can be processed

                        if job.has_failed_dep():
                            # Cannot be scheduled for dep purposes
                            # push it to publisher
                            self.publish_failed_to_run_job(job, Test.NOSTART_STR, Test.State.ERR_DEP)
                            # Attempt to find another job to schedule
                            continue

                        # Reached IF Job hasn't be run yet
                        # Job has completed its dep scheme
                        # all deps are successful
                        # => SCHEDULE
                        if user_sched_job:
                            pick_job = self._plugin.invoke_plugins(
                                                    Plugin.Step.SCHED_JOB_EVAL,
                                                    job=job,
                                                    set=the_set)
                        else:
                            pick_job = job.get_dim() <= max_dim
                            
                        if job.state != Test.State.IN_PROGRESS and pick_job:
                            job.pick()
                            if not the_set:
                                the_set = Set(execmode=Set.ExecMode.LOCAL)
                            the_set.add(job)
                            break
                        else:
                            if job.not_picked():
                                self.publish_failed_to_run_job(job, Test.MAXATTEMPTS_STR, Test.State.ERR_OTHER)
                            else:
                                self._dims[k].append(job)
        self._plugin.invoke_plugins(Plugin.Step.SCHED_SET_AFTER)
        return the_set

    def publish_failed_to_run_job(self, job, out, state):
        publish_job_args = {
            "rc": -1,
            "time": 0.0,
            "out": out,
            "state": state
        }
        self.publish_job(
            job, publish_args=publish_job_args)
        job.display()

    def merge_subset(self, set):
        """After completion, process the Set to publish test results.

        :param set: the set handling jobs during the scheduling.
        :type set: :class:`Set`
        """
        final = list()
        for job in set.content:
            if job.been_executed():
                job.extract_metrics()
                job.evaluate()
                self.publish_job(job, publish_args=None)
                job.display()
            else:
                
                if job.not_picked():
                    self.publish_failed_to_run_job(job, Test.MAXATTEMPTS_STR, Test.State.ERR_OTHER)
                else:
                    self.add_job(job)
