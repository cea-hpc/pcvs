import json
import os

from pcvs import NAME_BUILD_RESDIR
from pcvs.helpers.system import MetaConfig, ValidationScheme
from pcvs.plugins import Plugin


class Publisher:
    """Manage result publication and storage on disk.

    Jobs are submitted to a publisher, forming a set of ready-to-be-flushed
    elements. Every time `generate_file` is invoked, tests are dumped to a file
    named after ``pcvs_rawdat<id>.json``, where ``id`` is a automatic increment.
    Then, pool is emptied and waiting for new tests. This way, a single manager
    manages multiple files. 

    :cvar scheme: path to test result scheme
    :type scheme: str
    :cvar increment: used within filename
    :type increment: int
    :cvar fn_fmt: filename format string
    :type fn_fmt: str

    :ivar _layout: hierarchical representation of tests within the file
    :type _layout: dict
    :ivar _destpath: target filepath
    :type _destpath: str
    """
    scheme = None
    increment = 0
    fn_fmt = "pcvs_rawdat{:>04d}.json"

    def __init__(self, prefix="."):
        """constructor method.

        :param prefix: where result file will be stored in
        :type prefix: str
        """
        super().__init__()
        self._layout = {
            "tests": []
        }
        self._destpath = os.path.join(prefix, NAME_BUILD_RESDIR)
        assert(os.path.isdir(self._destpath))

    @property
    def format(self):
        """Return format type (currently only 'json' is supported).

        :return: format as printable string
        :rtype: str
        """
        return "json"

    def empty_entries(self):
        """Empty the publisher from all saved jobs."""
        self._layout['tests'] = list()

    def validate(self, stream):
        """Ensure the test results layout saved is compliant with standards.

        :param stream: content to validate against publisher scheme.
        :type: stream: dict or str
        """
        if not self.scheme:
            self.scheme = ValidationScheme("test-result")

        self.scheme.validate(stream)

    def add(self, json):
        """Add a new job to be published.

        :param json: the Test() JSON.
        :type json: json
        """
        self.validate(json)
        self._layout['tests'].append(json)

    def flush(self):
        """Flush down saved JSON-based jobs to a single file. 

        The Publisher is then reset for the next flush (next file).
        """
        MetaConfig.root.get_internal('pColl').invoke_plugins(
            Plugin.Step.SCHED_PUBLISH_BEFORE)
        # nothing to flush since the last call
        if len(self._layout['tests']) <= 0:
            return

        filename = os.path.join(
            self._destpath, self.fn_fmt.format(Publisher.increment))
        assert(not os.path.isfile(filename))

        Publisher.increment += 1

        with open(filename, 'w+') as fh:
            json.dump(self._layout, fh)
            self.empty_entries()

        MetaConfig.root.get_internal('pColl').invoke_plugins(
            Plugin.Step.SCHED_PUBLISH_BEFORE)
