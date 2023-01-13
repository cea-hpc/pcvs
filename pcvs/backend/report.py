import json
import os
import tarfile
import tempfile
import random

from ruamel.yaml import YAML

from pcvs import NAME_BUILD_RESDIR, PATH_SESSION, io
from pcvs.backend.session import Session
from pcvs.helpers import log
from pcvs.helpers.system import MetaDict
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.testing.test import Test
from pcvs.webview import create_app, data_manager
from pcvs.helpers import utils
from pcvs.backend.session import list_alive_sessions

def start_server(report):
    """Initialize the Flask server, default to 5000.

    A random port is picked if the default is already in use.

    :return: the application handler
    :rtype: class:`Flask`
    """
    app = create_app(report)
    ret = app.run(host='0.0.0.0', port=int(
        os.getenv("PCVS_REPORT_PORT", 5000)), debug=True)

    return ret


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

    man = BuildDirectoryManager(buildir)
    dataman.insert_session(sid, {
        'buildpath': buildir,
        'state': Session.State.COMPLETED,
        'dirs': conf_yml.validation.dirs
    })
    for test in man.results.browse_tests():
        dataman.insert_test(sid, test)

    dataman.close_session(sid, {'state': Session.State.COMPLETED})

class Report:
    def __init__(self):
        self._sessions = dict()
        self._alive_session_infos = dict()
    
    def __create_build_handler(self, path):
        if utils.check_is_buildir(path):
            hdl = BuildDirectoryManager(path)
        elif utils.check_is_archive(path):
            hdl = BuildDirectoryManager.load_from_archive(path)
        else:
            raise Exception()
        return hdl
        
    def add_session(self, path):
        hdl = self.__create_build_handler(path)
        hdl.load_config()
        hdl.init_results()
        self._sessions[hdl.sid] = hdl
    
    def load_alive_sessions(self):
        """A issue with this function,  as invalid sessions are not managet yet."""
        self._alive_session_infos = list_alive_sessions()

        for sk, sv in self._alive_session_infos.items():
            hdl = self.__create_build_handler(sv['path'])
            if hdl.sid in self._sessions:
                #SID may be recycled
                # just attribute another number (negative, to make it noticeable)
                while hdl.sid in self._sessions:
                    hdl.sid = random.randint(0, 10000) * (-1)

            elif hdl.sid != sk:
                #The build directory has been reused since this session ended
                #mark the old one as 'unavailable'
                pass

            self.add_session(sv['path'])

    @property
    def session_ids(self) -> list:
        return list(self._sessions.keys())
    
    @classmethod
    def dict_convert_list_to_cnt(self, l):
        return {k: len(v) for k, v in l.items()}
        
    def session_infos(self) -> dict:
        res = []
        for sid in self._sessions:
            counts = self.dict_convert_list_to_cnt(self.single_session_status(sid))
            state = self._alive_session_infos[sid]['state'] if sid in self._alive_session_infos else Session.State.COMPLETED
            res.append({'sid': sid,
                        'state': str(state),
                        'count': counts,
                        'path': self._sessions[sid].prefix})
        return res

    def single_session_status(self, sid, filter=None):
        assert sid in self._sessions
        statuses = self._sessions[sid].results.status_view
        if filter:
            assert(filter in statuses)
            return statuses[filter]
        else:
            return statuses
    
    def single_session_tags(self, sid):
        assert sid in self._sessions
        return self._sessions[sid].results.tags_view
    
    def single_session_job_cnt(self, sid):
        assert sid in self._sessions
        return self._sessions[sid].results.total_cnt
    
    def single_session_labels(self, sid):
        assert sid in self._sessions
        labels_info = self._sessions[sid].results.tree_view
        return {label: labels_info[label] for label in self._sessions[sid].config.validation.dirs.keys()}

    def single_session_build_path(self, sid):
        assert sid in self._sessions
        return self._sessions[sid].prefix
    
    def single_session_map_id(self, sid, jid):
        assert sid in self._sessions
        return self._sessions[sid].results.map_id(id=jid)

    def single_session_get_view(self, sid, name, subset=None, summary=False):
        d = {}
        if name == "tags":
            d = self.single_session_tags(sid)
        elif name == "labels":
            d = self.single_session_labels(sid)
        else:
            return None
        
        if subset:
            d = {k: v for k, v in d.items() if subset in k}
            
        if d and summary:
            return {k: self.dict_convert_list_to_cnt(v) for k, v in d.items()}
        else:
            return d
    
    
def build_static_pages(buildir):
    """From a given build directory, generate static pages.

    This can be used only for already run test-suites (no real-time support) and
    when Flask cannot/don't want to be used.

    :param buildir: the build directory to load
    :type buildir: str
    """
    raise Exception()
