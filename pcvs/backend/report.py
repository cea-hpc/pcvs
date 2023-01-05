import json
import os
import tarfile
import tempfile

from ruamel.yaml import YAML

from pcvs import NAME_BUILD_RESDIR
from pcvs import io
from pcvs.backend.session import Session
from pcvs.helpers import log
from pcvs.helpers.system import MetaDict
from pcvs.testing.test import Test
from pcvs.webview import create_app
from pcvs.webview import data_manager
from pcvs.orchestration import Publisher

def locate_json_files(path):
    """Locate where json files are stored under the given prefix.

    :param path: [description]
    :type path: [type]
    :return: [description]
    :rtype: [type]
    """
    array = list()
    for f in os.listdir(path):
        if f.startswith("pcvs_rawdat") and f.endswith(".json"):
            array.append(os.path.join(path, f))

    return array


def start_server():
    """Initialize the Flask server, default to 5000.

    A random port is picked if the default is already in use.

    :return: the application handler
    :rtype: class:`Flask`
    """
    app = create_app()
    ret = app.run(host='0.0.0.0', port=int(
        os.getenv("PCVS_REPORT_PORT", 5000)))

    return app


def upload_buildir_results(buildir):
    """Upload a whole test-suite from disk to the server data model.

    :param buildir: the build directory
    :type buildir: str
    """

    # first, need to determine the session ID -> conf.yml
    with open(os.path.join(buildir, "conf.yml"), 'r') as fh:
        conf_yml = MetaDict(YAML().load(fh))

    sid = conf_yml.validation.sid
    dataman = data_manager

    result_dir = os.path.join(buildir, NAME_BUILD_RESDIR)
    dataman.insert_session(sid, {
        'buildpath': buildir,
        'state': Session.State.COMPLETED,
        'dirs': conf_yml.validation.dirs
    })

    pub = Publisher(result_dir)
    for test in pub.browse_tests():
        print(test)
        dataman.insert_test(sid, test)

    dataman.close_session(sid, {'state': Session.State.COMPLETED})


def upload_buildir_results_from_archive(archive):
    with tempfile.TemporaryDirectory() as tempdir:
        archive = os.path.abspath(archive)
        tarfile.open(archive).extractall(tempdir)
        upload_buildir_results(os.path.join(tempdir, "save_for_export"))


def build_static_pages(buildir):
    """From a given build directory, generate static pages.

    This can be used only for already run test-suites (no real-time support) and
    when Flask cannot/don't want to be used.

    :param buildir: the build directory to load
    :type buildir: str
    """
    with open(os.path.join(buildir, "conf.yml"), 'r') as fh:
        conf_yml = MetaDict(YAML().load(fh))

    sid = conf_yml.validation.sid

    result_dir = os.path.join(buildir, 'rawdata')
    for f in os.listdir(result_dir):
        pass
