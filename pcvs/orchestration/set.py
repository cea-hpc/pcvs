import subprocess
import threading
import time
from typing import List

from pcvs.helpers import communications, log
from pcvs.helpers.system import MetaConfig
from pcvs.testing.test import Test

comman: communications.GenericServer = None


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