import queue
import subprocess
import threading
import time
from typing import List

from pcvs.helpers import communications
from pcvs.helpers.system import MetaConfig
from pcvs.testing.test import Test


class Set:
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
    comman: communications.GenericServer = None

    def __init__(self):
        """constructor method."""
        self._id = Set.global_increment
        Set.global_increment += 1
        self._size = 0
        self._jobs: List[Test] = list()
        self._completed = False
        self._is_wrapped = False

        if not self.comman:
            if MetaConfig.root.get_internal('comman') is not None:
                self.comman = MetaConfig.root.get_internal('comman')

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

    def is_complete(self):
        self._completed = True


class Runner(threading.Thread):

    sched_in_progress = True

    def __init__(self, ready, complete):
        super().__init__()

        self._rq = ready
        self._cq = complete

    def run(self):
        while True:
            try:
                if self.sched_in_progress:
                    item = self._rq.get(block=False, timeout=5)
                    self.process_item(item)
                    self._cq.put(item)
                else:
                    break
            except queue.Empty:
                continue
            except Exception:
                print("end thread")
                return

    def process_item(self, set):
        """Execute the Set and jobs within it.

        :raises Exception: Something occured while running a test"""
        for job in set.content:
            try:
                p = subprocess.Popen('{}'.format(job.invocation_command),
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

            if set.comman:
                set.comman.send(job)

        set.is_complete()
