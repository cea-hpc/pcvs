import queue

from pcvs.backend import session
from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.manager import Manager
from pcvs.orchestration.publishers import Publisher
from pcvs.orchestration.set import Runner, Set
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


def global_stop():
    Orchestrator.stop()


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
        self._runners = list()
        self._max_res = config_tree.machine.get('nodes', 1)
        self._publisher = Publisher(config_tree.validation.output)
        self._manager = Manager(self._max_res, publisher=self._publisher)
        self._maxconcurrent = config_tree.machine.get('concurrent_run', 1)
        self._complete_q = queue.Queue()
        self._ready_q = queue.Queue()

    def print_infos(self):
        """display pre-run infos."""
        log.manager.print_item("Test count: {}".format(
            self._manager.get_count('total')))
        log.manager.print_item(
            "Max simultaneous Sets: {}".format(self._maxconcurrent))
        log.manager.print_item("Resource count: {}".format(self._max_res))

    # This func should only be a passthrough to the job manager
    def add_new_job(self, job):
        """Append a new job to be scheduled.

        :param job: job to append
        :type job: :class:`Test`
        """
        self._manager.add_job(job)

    @log.manager.capture_exception(KeyboardInterrupt, global_stop)
    def start_run(self, the_session=None, restart=False):
        """Start the orchestrator.

        :param the_session: container owning the run.
        :type the_session: :class:`Session`
        :param restart: whether the run is starting from scratch
        :type restart: False for a brand new run.
        """

        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.SCHED_BEFORE)

        for i in range(0, self._maxconcurrent):
            self.start_new_runner()

        self._manager.resolve_deps()

        nb_nodes = self._max_res
        last_progress = 0
        # While some jobs are available to run
        while self._manager.get_leftjob_count() > 0 or not self._ready_q.empty():
            # dummy init value
            new_set: Set = not None
            while new_set is not None:
                # create a new set, if not possible, returns None
                new_set = self._manager.create_subset(nb_nodes)
                if new_set is not None:
                    # schedule the set asynchronously
                    nb_nodes -= new_set.dim
                    self._ready_q.put(new_set)

            # Now, look for a completion
            try:
                set = self._complete_q.get(block=False, timeout=2)
                nb_nodes += set.dim
                self._manager.merge_subset(set)
            except queue.Empty:
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

        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.SCHED_AFTER)

        self.stop_runners()

        return 0 if self._manager.get_count('total') - self._manager.get_count(Test.State.SUCCESS) == 0 else 1

    def start_new_runner(self):
        """Start a new Runner thread & register comm queues."""
        Runner.sched_in_progress = True
        r = Runner(ready=self._ready_q, complete=self._complete_q)
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
        Runner.sched_in_progress = False

    def run(self, session):
        """Start the orchestrator.

        :param session: container owning the run.
        :type session: :class:`Session`
        """
        # pre-actions done only once
        return self.start_run(session, restart=False)
