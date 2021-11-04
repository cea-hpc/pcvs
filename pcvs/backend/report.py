import json
import os

from ruamel.yaml import YAML

from pcvs.backend.session import Session
from pcvs.helpers import log
from pcvs.helpers.system import MetaDict
from pcvs.testing.test import Test
from pcvs.webview import create_app, data_manager


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
    app = None
    for port in [5000, 0]:
        try:
            app = create_app()
            app.run(host='0.0.0.0', port=port)
            break
        except OSError as e:
            print("Fail to run on port {}. Try automatically-defined".format(port))
            continue
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

    result_dir = os.path.join(buildir, 'rawdata')
    dataman.insert_session(sid, {
        'buildpath': buildir,
        'state': Session.State.COMPLETED,
        'dirs': conf_yml.validation.dirs
    })

    for f in os.listdir(result_dir):
        assert(f.endswith(".json"))
        log.manager.info("Loading {}".format(os.path.join(result_dir, f)))

        with open(os.path.join(result_dir, f), 'r') as fh:
            data = json.load(fh)
            for t in data["tests"]:
                obj = Test()
                obj.from_json(t)
                dataman.insert_test(sid, obj)

    dataman.close_session(sid, {'state': Session.State.COMPLETED})


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
