import os

from pcvs.backend.report import Report
from pcvs.helpers.utils import check_is_archive, check_is_buildir
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.testing.test import Test


class ReportModel(Report):
    def __init__(self, build_paths):
        
        assert(isinstance(build_paths, list))
        super().__init__()
        self.active_hdl = None
        for path in build_paths:
            hdl = self.add_session(path)
            if not self.active_hdl:
                self.active_hdl = hdl
        
    @property
    def active(self):
        return self.active_hdl
    
    @property
    def active_id(self):
        return self.active_hdl.sid

    @property
    def session_prefixes(self):
        return [x['path'] for x in self.session_infos()]

    
    def set_active(self, hdl):
        if isinstance(hdl, str):
            for v in self._sessions.values():
                if hdl == v.prefix:
                    hdl = v
                    break
        self.active_hdl = hdl
        
    def pick_color_on_status(self, state: Test.State):
        if state == Test.State.FAILURE:
            return "red bold"
        elif state == Test.State.SUCCESS:
            return "green"
        else:
            return "yellow italic"
                