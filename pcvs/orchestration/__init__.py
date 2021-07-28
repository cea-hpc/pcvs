from pcvs.plugins import Plugin
from pcvs.backend import session
from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig
from pcvs.orchestration.publishers import Publisher
from pcvs.orchestration.set import Set
from pcvs.orchestration.manager import Manager


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
        self._max_res = config_tree.machine.get('nodes', 1)
        self._publisher = Publisher(config_tree.validation.output)
        self._manager = Manager(self._max_res, publisher=self._publisher)
        self._maxconcurrent = config_tree.machine.concurrent_run

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

    def start_run(self, the_session=None, restart=False):
        """Start the orchestrator.

        :param the_session: container owning the run.
        :type the_session: :class:`Session`
        :param restart: whether the run is starting from scratch
        :type restart: False for a brand new run.
        """
        
        MetaConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.SCHED_BEFORE)
        
        self._manager.resolve_deps()
        
        nb_nodes = self._max_res
        last_progress = 0
        # While some jobs are available to run
        while self._manager.get_leftjob_count() > 0 or len(self._pending_sets) > 0:
            # dummy init value
            new_set: Set = not None
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
    
        MetaConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.SCHED_AFTER)

    def run(self, session):
        """Start the orchestrator.

        :param session: container owning the run.
        :type session: :class:`Session`
        """
        # pre-actions done only once
        self.start_run(session, restart=False)
        pass
