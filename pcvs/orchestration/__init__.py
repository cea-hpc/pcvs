import subprocess
import threading
import time
from typing import List

from addict import Dict

from pcvs.backend import session
from pcvs.helpers import communications, log
from pcvs.helpers.exceptions import OrchestratorException
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.publishers import Publisher
from pcvs.testing.test import Test

comman: communications.GenericServer = None

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
        self._dims = dict()
        self._max_size = max_size
        self._publisher = publisher
        self._count = Dict({
            "total": 0,
            "executed": 0
        })

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

        for depname, depobj in job.deps.items():
            if depobj is None:
                hashed_dep = hash(depname)
                if hashed_dep not in self.job_hashes:
                    raise OrchestratorException.UndefDependencyError(depname)

                job_dep = self.job_hashes[hashed_dep]

                if job_dep.name in chain:
                    raise OrchestratorException.CircularDependencyError(
                        job_dep.name)

                self.resolve_single_job_deps(job_dep, chain)
                job.set_dep(depname, job_dep)

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
                            if comman:
                                comman.send(job)
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


class Set(threading.Thread):
    """Gather multiple jobs to be scheduled.

    Created by the manager to manipulate a subset, these jobs are removed from
    the manager during the execution, only reachable from a Set. Sets are
    launched as thread, dealing with their own workflow.

    :ivar _id: unique id
    :type _id: int
    :ivar _size: number of jobs
    :type _size: int
    :ivar _jobs: list of jobs
    :type _jobs: list
    :ivar _completed: True if all jobs have been executed
    :type _completed: bool
    :ivar _is_wrapped: not used yet
    :type _is_wrapped: bool
    """
    global_increment = 0

    def __init__(self):
        """constructor method."""
        self._id = Set.global_increment
        Set.global_increment += 1
        self._size = 0
        self._jobs: List[Test] = list()
        self._completed = False
        self._is_wrapped = False
        super().__init__()

    def enable_wrapping(self, wrap_cli):
        """Make this Set manipulate multiple jobs evolving together in a
        dedicated environment.

        .. warning::
            WIP

        :param wrap_cli: noit used yet
        :type wrap_cli: str
        """
        self._wrap_cmd = wrap_cli
        self._is_wrapped = True

    def add(self, l):
        """Add a job or a list of jobs to the current Set.

        :param l: a single or a list of jobs
        :type l: :class:`Test` or List[:class:`Test`]
        """
        if not isinstance(l, list):
            l = [l]
        self._jobs += l
        self._size = len(self._jobs)

    def is_empty(self):
        """check is the set is empty (contains no jobs)

        :return: True if there is no jobs
        :rtype: bool
        """
        return len(self._jobs) == 0

    def been_completed(self):
        """check is the Set is complete and can be flushed down to the manager.

        :return: True if all jobs have been completed.
        :rtype: bool
        """
        return self._completed

    @property
    def size(self):
        """Getter to size property.

        :return: Set size
        :rtype: int
        """
        return self._size

    @property
    def id(self):
        """Getter to id property.

        :return: Set id
        :rtype: int
        """
        return self._id

    @property
    def dim(self):
        """Getter to dim property (largest dimension of a single job)

        :return: Set dim
        :rtype: int
        """
        if self._size <= 0:
            return 0
        elif self._size == 1:

            return self._jobs[0].get_dim()
        else:
            return max(self._jobs, key=lambda x: x.get_dim())

    @property
    def content(self):
        """Generator iterating over the job list."""
        for j in self._jobs:
            yield j

    def run(self):
        """Execute the Set and jobs within it.

        :raises Exception: Something occured while running a test"""
        for job in self._jobs:
            try:
                p = subprocess.Popen('{}'.format(job.wrapped_command),
                                     shell=True,
                                     stderr=subprocess.STDOUT,
                                     stdout=subprocess.PIPE)
                start = time.time()
                stdout, _ = p.communicate(timeout=job.timeout)
                final = time.time() - start

                # Note: The return code here is coming from the script,
                # not the test itself. It is transitively transmitted once the
                # test complete, except if test used matchers to validate.
                # in that case, a non-zero exit code indicates at least one
                # matcher failed.
                # The the engine, no other checks than return code evaluation
                # is necessary to assess test status.
                rc = p.returncode

            except subprocess.TimeoutExpired:
                p.kill()
                final = job.timeout
                stdout, _ = p.communicate()
                rc = Test.Timeout_RC  # nah, to be changed
            except Exception:
                raise
            job.save_final_result(time=final, rc=rc, out=stdout)
            job.display()
            if comman:
                comman.send(job)

        self._completed = True


class Orchestrator:
    """The job orchestrator, managing test processing through the whole test base.

    :ivar _conf: global configuration object
    :type _conf: :class:`MetaConfig`
    :ivar _pending_sets: started Sets not completed yet
    :type _pending_sets: list
    :ivar _max_res: number of resources allowed to be used
    :type _max_res: int
    :ivar _publisher: result publisher
    :type _publisher: :class:`Publisher`
    :ivar _manager: job manager
    :type _manager: :class:`Manager`
    :ivar _maxconcurrent: Max number of sets started at the same time.
    :type _maxconcurrent: int

    """

    def __init__(self):
        """constructor method"""
        config_tree = MetaConfig.root
        self._conf = config_tree
        self._pending_sets = dict()
        self._max_res = config_tree.machine.nodes
        self._publisher = Publisher(config_tree.validation.output)
        self._manager = Manager(self._max_res, publisher=self._publisher)
        self._maxconcurrent = config_tree.machine.concurrent_run

    def print_infos(self):
        """display pre-run infos."""
        log.manager.print_item("Total base: {} test(s)".format(
            self._manager.get_count('total')))
        log.manager.print_item(
            "Concurrent launches: {} job(s)".format(self._maxconcurrent))
        log.manager.print_item("Number of resources: {}".format(self._max_res))

    # This func should only be a passthrough to the job manager
    def add_new_job(self, job):
        """Append a new job to be scheduled.

        :param job: job to append
        :type job: :class:`Test`
        """
        self._manager.add_job(job)

    def start_run(self, the_session=None, restart=False):
        """Start the orchestrator.

        :param the_session: container owning the run.
        :type the_session: :class:`Session`
        :param restart: whether the run is starting from scratch
        :type restart: False for a brand new run.
        """
        self._manager.resolve_deps()
        self.print_infos()
        
        global comman
        comman = MetaConfig.root.get_internal('comman')

        nb_nodes = self._max_res
        last_progress = 0
        # While some jobs are available to run
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
                # TODO: create backup to allow start/stop

            current_progress = self._manager.get_count(
                'executed') / self._manager.get_count('total')

            # Condition to trigger a dump of results
            # info result file at a periodic step of 5% of
            # the global workload
            if (current_progress - last_progress) > 0.05:
                # TODO: Publish results periodically
                # 1. on file system
                # 2. directly into the selected bank
                self._publisher.flush()
                last_progress = current_progress
                if the_session is not None:
                    session.update_session_from_file(
                        the_session.id, {'progress': current_progress * 100})

        self._publisher.flush()
        assert(self._manager.get_count('executed')
               == self._manager.get_count('total'))

    def run(self, session):
        """Start the orchestrator.

        :param session: container owning the run.
        :type session: :class:`Session`
        """
        # pre-actions done only once
        self.start_run(session, restart=False)
        pass
