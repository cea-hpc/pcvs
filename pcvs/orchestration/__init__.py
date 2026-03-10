import queue
from queue import Queue

from pcvs import io
from pcvs.backend import session
from pcvs.backend.metaconfig import GlobalConfig
from pcvs.backend.session import Session
from pcvs.helpers.resource_tracker import ResourceTracker
from pcvs.io import Verbosity
from pcvs.orchestration.manager import Manager
from pcvs.orchestration.runner import RunnerAdapter
from pcvs.orchestration.set import Set
from pcvs.plugins import Plugin
from pcvs.testing.test import Test
from pcvs.testing.teststate import TestState


def global_stop(e: Exception | KeyboardInterrupt) -> None:
    Orchestrator.stop()
    raise e


class Orchestrator:
    """The job orchestrator, managing test processing through the whole test base.

    :ivar _conf: global configuration object
    :type _conf: :class:`MetaConfig`
    :ivar _pending_sets: started Sets not completed yet
    :type _pending_sets: list
    :ivar _max_nodes: number of nodes allowed to be used
    :type _max_nodes: int
    :ivar _max_cores: number of cores allowed to be used
    :type _max_cores: int
    :ivar _publisher: BuildDirectoryManager
    :type _publisher: :class:`BuildDirectoryManager`
    :ivar _manager: job manager
    :type _manager: :class:`Manager`
    :ivar _maxconcurrent: Max number of sets started at the same time.
    :type _maxconcurrent: int
    """

    def __init__(self) -> None:
        """constructor method"""
        config_tree = GlobalConfig.root
        # TODO: make meta config an argument and stop relying on global config
        self._runners: list[RunnerAdapter] = []
        self._max_nodes = config_tree["machine"].get("nodes", 1)
        self._max_cores = config_tree["machine"].get("cores_per_node", 1)
        self._resources_tracker = ResourceTracker([self._max_nodes, self._max_cores])
        self._publisher = config_tree.get_internal("build_manager").results
        self._manager = Manager(self._max_nodes, publisher=self._publisher)
        self._maxconcurrent = config_tree["machine"].get("concurrent_run", 1)
        self._complete_q: Queue = Queue()
        self._ready_q: Queue = Queue()

    def print_infos(self) -> None:
        """display pre-run infos."""
        io.console.print_item("Test count: {}".format(self._manager.get_count("total")))
        io.console.print_item("Max simultaneous Sets: {}".format(self._maxconcurrent))
        io.console.print_item("Configured available nodes: {}".format(self._max_nodes))

    # This func should only be a passthrough to the job manager
    def add_new_job(self, job: Test) -> None:
        """Append a new job to be scheduled.

        :param job: job to append
        """
        self._manager.add_job(job)

    def compute_deps(self) -> None:
        """Compute tests dependencies and filter tests based on tags."""
        self._manager.resolve_deps()
        if io.console.verbosity >= Verbosity.DEBUG:
            self._manager.print_dep_graph("./graph.dat")
        # filter test that should be run based on tags
        # this need to be done after the deps are computed to avoid
        # removing test dependency that are not tagged
        self._manager.filter_tags()
        if io.console.verbosity >= Verbosity.DEBUG:
            self._manager.print_dep_graph("./graph-filter.dat")

    # TODO implement restart so the session does not have
    # to restart from scratch each time
    @io.capture_exception(KeyboardInterrupt, global_stop)
    def start_run(
        self,
        the_session: Session | None = None,
        restart: bool = False,  # pylint: disable=unused-argument
    ) -> int:
        """Start the orchestrator.

        :param the_session: The session owning the run.
        :param restart: Whether the run is starting from scratch. (Unsupord)
        :return: the return code for the run. (0 if no test fail otherwise 1)
        """
        assert not restart  # restart is not supported yet !!

        GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.SCHED_BEFORE)

        io.console.info("ORCH: initialize runners")
        for _ in range(0, self._maxconcurrent):
            self.start_new_runner()

        # track number of currently scheduled jobs.
        currently_scheduled_count = 0

        last_progress = 0.0
        io.console.info("ORCH: start job scheduling")
        self._manager.create_job_cache()
        # While some jobs are available to run
        with io.console.table_container(self._manager.get_count()):
            while self._manager.get_leftjob_count() > 0:
                # dummy init value
                new_set: Set | None = Set()
                # Add new tests to the queue
                while new_set is not None:
                    # create a new set, if not possible, returns None
                    new_set = self._manager.create_subset(self._resources_tracker)
                    if new_set is not None:
                        currently_scheduled_count += new_set.size
                        # schedule the set asynchronously
                        io.console.sched_debug(
                            "ORCH: send Set to queue (#{}, sz:{})".format(new_set.id, new_set.size)
                        )
                        self._ready_q.put(new_set)
                if currently_scheduled_count == 0:
                    nb_jobs = self._manager.get_leftjob_count()
                    if nb_jobs > 0:
                        io.console.error(
                            f"Job scheduler stuck, fail to schedule {nb_jobs} jobs !!!"
                        )
                        self._manager.prune_all_jobs_as_non_runnable()
                # Look for tests completions
                try:
                    # while queue is not empty
                    jobs: Set = self._complete_q.get(block=True, timeout=1)
                    currently_scheduled_count -= jobs.size
                    while True:
                        io.console.sched_debug(
                            "ORCH: recv Set from queue (#{}, sz:{})".format(jobs.id, jobs.size)
                        )
                        for job in jobs.content:
                            self._resources_tracker.free(job.alloc_tracking)
                            io.console.sched_debug(
                                f"Alloc pool (FREE) {job.alloc_tracking}:"
                                f" {self._resources_tracker}"
                            )
                        self._manager.merge_subset(jobs)
                        # Continue to gather resultes as long as some are available.
                        jobs = self._complete_q.get(block=False)
                except queue.Empty:
                    pass

                # compute progress status
                current_progress = self._manager.get_count("executed") / self._manager.get_count(
                    "total"
                )

                # TODO: create backup to allow start/stop from these files
                # Condition to trigger a dump of results
                # info result file at a periodic step of 5% of
                # the global workload
                if (current_progress - last_progress) > 0.05:
                    # Publish results periodically
                    # 1. on file system
                    #    => Done
                    # 2. directly into the selected bank
                    #    => NO NEVER, not until the end of the test
                    #       at risk of bank corruption
                    io.console.sched_debug("ORCH: Flush a new progression file")
                    self._publisher.flush()
                    last_progress = current_progress
                    if the_session is not None:
                        session.update_session_from_file(
                            the_session.id, {"progress": current_progress * 100}
                        )

        # need a new line to flush after the table container if outputting to a file
        io.console.print("")
        self._publisher.flush()
        assert self._manager.get_count("executed") == self._manager.get_count("total")

        GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.SCHED_AFTER)

        io.console.info("ORCH: Stop active runners")
        self.stop_runners()

        return (
            0
            if self._manager.get_count("total") - self._manager.get_count(str(TestState.SUCCESS))
            == 0
            else 1
        )

    def start_new_runner(self) -> None:
        """Start a new Runner thread & register comm queues."""
        RunnerAdapter.sched_in_progress = True
        r = RunnerAdapter(
            buildir=GlobalConfig.root["validation"]["output"],
            ready=self._ready_q,
            complete=self._complete_q,
        )
        r.start()
        self._runners.append(r)

    def stop_runners(self) -> None:
        """Stop all previously started runners.

        Wait for their completion."""
        self.stop()
        for t in self._runners:
            t.join()

    @classmethod
    def stop(cls) -> None:
        """Request runner threads to stop."""
        RunnerAdapter.sched_in_progress = False

    def run(self, s: Session) -> int:
        """Start the orchestrator.

        :param s: container owning the run.
        :return: The exist code of the session.
        """
        # pre-actions done only once
        return self.start_run(s, restart=False)  # type: ignore
