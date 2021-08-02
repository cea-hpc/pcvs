from pcvs.helpers import communications, log
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
    :type _publisher: :class:`Publisher`
    :ivar _count: dict gathering various counters (total, executed...)
    :type _count: dict 
    """
    job_hashes = dict()

    def __init__(self, max_size=0, builder=None, publisher=None):
        """constructor method.

        :param max_size: max number of resource allowed to schedule.
        :type max_size: int
        :param builder: Not used yet
        :type builder: None
        :param publisher: requested publisher by the orchestrator
        :type publisher: :class:`Publisher`
        """
        self._comman = MetaConfig.root.get_internal('comman')
        self._plugin = MetaConfig.root.get_internal('pColl')

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

        hashed = hash(job.name)
        # if test is not know yet, add + increment
        if hashed not in self.job_hashes:
            self.job_hashes[hash(job.name)] = job
            self._count.total += 1

    def get_count(self, tag="total"):
        """Access to a particular counter.

        :param tag: a specific counter to target, defaults to "total"
        :type tag: str
        :return: a count
        :rtype: int
        """
        assert(tag in self._count.keys())
        return self._count[tag]

    def resolve_deps(self):
        """Resolve the whole dependency graph.

        This function is meant to be called once and browse every single tests
        to resolve dep names to their real associated object.
        """
        for joblist in self._dims.values():
            for job in joblist:
                self.resolve_single_job_deps(job, list())

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

            hashed_dep = hash(depname)
            if hashed_dep not in self.job_hashes:
                raise OrchestratorException.UndefDependencyError(depname)

            job_dep = self.job_hashes[hashed_dep]

            if job_dep.name in chain:
                raise OrchestratorException.CircularDependencyError(
                    job_dep.name)
            self.resolve_single_job_deps(job_dep, chain)
            job.resolve_a_dep(depname, job_dep)

    def get_leftjob_count(self):
        """Return the number of jobs remainig to be executed.

        :return: a number of jobs
        :rtype: int
        """
        return self._count.total - self._count.executed

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

        if self._plugin.has_step(Plugin.Step.SCHED_SET_EVAL):
            the_set = self._plugin.invoke_plugins(
                Plugin.Step.SCHED_SET_EVAL,
                jobman=self,
                max_dim=max_dim
            )
        else:
            for k in sorted(self._dims.keys(), reverse=True):
                if len(self._dims[k]) <= 0:
                    continue
                else:
                    # assert(self._builder.job_grabber)
                    job: Test = self._dims[k].pop()

                    if job:
                        if job.been_executed() or job.has_failed_dep():
                            # jobs can be picked up outside of this pop() call
                            # if tagged executed, they have been fully handled
                            # and should just be removed from scheduling
                            #
                            # Another case: test can't be picked up because
                            # job deps have failed.
                            # in that case, no job management occured.
                            # do it now.
                            if job.has_failed_dep():
                                job.save_final_result(rc=-1, time=0.0,
                                                      out=Test.NOSTART_STR,
                                                      state=Test.State.ERR_DEP)
                                job.display()
                                if self._comman:
                                    self._comman.send(job)
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
                        job.pick()
                        the_set = Set()
                        the_set.add(job)
                        break

        self._plugin.invoke_plugins(Plugin.Step.SCHED_SET_AFTER)

        return the_set

    def merge_subset(self, set):
        """After completion, process the Set to publish test results.

        :param set: the set handling jobs during the scheduling.
        :type set: :class:`Set`
        """
        final = list()
        for job in set.content:
            if job.been_executed():
                self._count.executed += 1
                self._publisher.add(job.to_json())
            else:
                self.add_job(job)
