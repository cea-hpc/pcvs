import os
import queue

from pcvs import NAME_BUILD_RESDIR, io
from pcvs.backend import session
from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.manager import Manager
from pcvs.orchestration.set import Set
from pcvs.orchestration.runner import RunnerAdapter
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


def global_stop(e):
    Orchestrator.stop()
    raise e


class Orchestrator:
    """The job orchestrator, managing test processing through the whole test base.

    :ivar _conf: global configuration object
    :type _conf: :class:`MetaConfig`
    :ivar _pending_sets: started Sets not completed yet
    :type _pending_sets: list
    :ivar _max_res: number of resources allowed to be used
    :type _max_res: int
    :ivar _publisher: Result File Manager
    :type _publisher: :class:`ResultFileManager`
    :ivar _manager: job manager
    :type _manager: :class:`Manager`
    :ivar _maxconcurrent: Max number of sets started at the same time.
    :type _maxconcurrent: int

    """

    def __init__(self):
        """constructor method"""
        config_tree = MetaConfig.root
        self._conf = config_tree
        self._runners = list()
        self._max_res = config_tree.machine.get('nodes', 1)
        self._publisher = config_tree.get_internal('build_manager').results
        self._manager = Manager(self._max_res, publisher=self._publisher)
        self._maxconcurrent = config_tree.machine.get('concurrent_run', 1)
        self._complete_q = queue.Queue()
        self._ready_q = queue.Queue()

    def print_infos(self):
        """display pre-run infos."""
        io.console.print_item("Test count: {}".format(
            self._manager.get_count('total')))
        io.console.print_item(
            "Max simultaneous Sets: {}".format(self._maxconcurrent))
        io.console.print_item("Resource count: {}".format(self._max_res))

    # This func should only be a passthrough to the job manager
    def add_new_job(self, job):
        """Append a new job to be scheduled.

        :param job: job to append
        :type job: :class:`Test`
        """
        self._manager.add_job(job)

    @io.capture_exception(KeyboardInterrupt, global_stop)
    def start_run(self, the_session=None, restart=False):
        """Start the orchestrator.

        :param the_session: container owning the run.
        :type the_session: :class:`Session`
        :param restart: whether the run is starting from scratch
        :type restart: False for a brand new run.
        """

        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.SCHED_BEFORE)

        io.console.info("ORCH: initialize runners")
        for i in range(0, self._maxconcurrent):
            self.start_new_runner()

        self._manager.resolve_deps()
        if io.console.verb_debug:
            self._manager.print_dep_graph(outfile="./graph.dat")

        nb_res = self._max_res
        last_progress = 0
        pending_list = list()
        io.console.info("ORCH: start job scheduling")
        # While some jobs are available to run
        with io.console.table_container(self._manager.get_count()):
            while self._manager.get_leftjob_count() > 0 or len(pending_list) > 0:
                # dummy init value
                new_set: Set = not None
                while new_set is not None:
                    # create a new set, if not possible, returns None
                    new_set = self._manager.create_subset(nb_res)
                    if new_set is not None:
                        assert(isinstance(nb_res, int))
                        # schedule the set asynchronously
                        nb_res -= new_set.dim
                        io.console.debug("ORCH: send Set to queue (#{}, sz:{})".format(
                            new_set.id, new_set.size))
                        self._ready_q.put(new_set)
                    else:
                        self._manager.prune_non_runnable_jobs()

                # Now, look for a completion
                try:
                    set = self._complete_q.get(block=False, timeout=2)
                    io.console.debug("ORCH: recv Set from queue (#{}, sz:{})".format(
                        set.id, set.size))
                    nb_res += set.dim
                    self._manager.merge_subset(set)
                except queue.Empty:
                    self._manager.prune_non_runnable_jobs()
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
                    io.console.debug("ORCH: Flush a new progression file")
                    self._publisher.flush()
                    last_progress = current_progress
                    if the_session is not None:
                        session.update_session_from_file(
                            the_session.id, {'progress': current_progress * 100})

        self._publisher.flush()
        assert (self._manager.get_count('executed')
                == self._manager.get_count('total'))

        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.SCHED_AFTER)

        io.console.info("ORCH: Stop active runners")
        self.stop_runners()

        return 0 if self._manager.get_count('total') - self._manager.get_count(Test.State.SUCCESS) == 0 else 1

    def start_new_runner(self):
        """Start a new Runner thread & register comm queues."""
        RunnerAdapter.sched_in_progress = True
        r = RunnerAdapter(buildir=MetaConfig.root.validation.output, ready=self._ready_q, complete=self._complete_q)
        r.start()
        self._runners.append(r)

    def stop_runners(self):
        """Stop all previously started runners.

        Wait for their completion."""
        self.stop()
        for t in self._runners:
            t.join()

    @classmethod
    def stop(cls):
        """Request runner threads to stop."""
        RunnerAdapter.sched_in_progress = False

    def run(self, session):
        """Start the orchestrator.

        :param session: container owning the run.
        :type session: :class:`Session`
        """
        # pre-actions done only once
        return self.start_run(session, restart=False)
