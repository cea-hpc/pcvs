import json
import yaml
from addict import Dict
import os

from pcvs.helpers.exceptions import ValidationException
from pcvs.helpers.system import ValidationScheme
from pcvs.testing.test import Test
from pcvs.webview import create_app, data_manager
from pcvs.backend.session import Session
from pcvs.helpers import log


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
    app = None
    for port in [5000, 0]:
        try:
            app = create_app().run(host='0.0.0.0', port=port)
            break
        except OSError as e:
            print("Fail to run on port {}. Try automatically-defined".format(port))
            continue
    return app

def upload_buildir_results(buildir):
    # first, need to determine the session ID -> conf.yml
    with open(os.path.join(buildir, "conf.yml"), 'r') as fh:
        conf_yml = Dict(yaml.load(fh, Loader=yaml.FullLoader))
    
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
    with open(os.path.join(buildir, "conf.yml"), 'r') as fh:
        conf_yml = Dict(yaml.load(fh, Loader=yaml.FullLoader))
    
    sid = conf_yml.validation.sid

    result_dir = os.path.join(buildir, 'rawdata')
    for f in os.listdir(result_dir):
        pass

