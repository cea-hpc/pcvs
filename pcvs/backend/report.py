import random
from typing import Any
from typing import Iterable

from pcvs.backend.session import list_alive_sessions
from pcvs.backend.session import SessionState
from pcvs.helpers import utils
from pcvs.helpers.exceptions import CommonException
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.testing.test import Test


class Report:
    """
    Map a Report interface, to handle request from frontends.
    """

    def __init__(self) -> None:
        """
        Initialize a new report
        """
        self._sessions: dict[str, BuildDirectoryManager] = {}
        self._alive_session_infos: dict[str, Any] = {}

    def __create_build_handler(self, path: str) -> BuildDirectoryManager:
        """
        Initialize a new handler to a build directory.

        This object will be used to forward result requests.

        :param path: build directory path
        :raises NotPCVSRelated: Invalid path is provided
        :return: the actual handler
        """
        if utils.check_is_buildir(path):
            hdl = BuildDirectoryManager(path)
        elif utils.check_is_archive(path):
            hdl = BuildDirectoryManager.load_from_archive(path)
        else:
            raise CommonException.NotPCVSRelated(
                reason="Given path is not PCVS build related", dbg_info={"path": path}
            )
        return hdl

    def add_session(self, path: str) -> BuildDirectoryManager:
        """
        Insert new session to be managed.

        :param path: the build path (root dir)
        :return: the session handler
        """
        hdl = self.__create_build_handler(path)
        hdl.load_config()
        hdl.init_results()
        self._sessions[hdl.sid] = hdl
        return hdl

    def load_alive_sessions(self) -> None:
        """
        Load currently active sessions as reference in PATH_SESSION.

        A issue with this function,  as invalid sessions are not manager yet.
        """
        self._alive_session_infos = list_alive_sessions()

        for sk, sv in self._alive_session_infos.items():
            hdl = self.__create_build_handler(sv["path"])
            if hdl.sid in self._sessions:
                # SID may be recycled
                # just attribute another number (negative, to make it noticeable)
                while hdl.sid in self._sessions:
                    hdl.sid = str(random.randint(0, 10000) * (-1))

            elif hdl.sid != sk:
                # The build directory has been reused since this session ended
                # mark the old one as 'unavailable'
                pass

            self.add_session(sv["path"])

    @property
    def session_ids(self) -> list[str]:
        """
        Get the list of session ids managed by this instance.

        :return: a list of session ids
        """
        return list(self._sessions.keys())

    def dict_convert_list_to_cnt(self, arrays: dict[str, list[str]]) -> dict[str, int]:
        """
        Convert dict of arrays to a dict of array lengths.

        Used to convert dict of per-status jobs to a summary of them.

        :param arrays: the dict of arrays
        :return: a summary of given dict
        """
        return {k: len(v) for k, v in arrays.items()}

    def session_infos(self) -> Iterable[dict[str, Any]]:
        """
        Get session metadata for each session currently loaded into the instance.
        """
        for sid, sdata in self._sessions.items():
            status_dict = self.single_session_status(sid)
            assert isinstance(status_dict, dict)
            counts = self.dict_convert_list_to_cnt(status_dict)
            state = (
                self._alive_session_infos[sid]["state"]
                if sid in self._alive_session_infos
                else SessionState.COMPLETED
            )
            yield {
                "sid": sid,
                "state": str(state),
                "count": counts,
                "path": sdata.prefix,
                "info": sdata.config["validation"].get("message", "No message"),
            }

    def single_session_config(self, sid: str) -> dict:
        """
        Get the configuration map from a single session.

        :param sid: the session ID
        :return: the configuration node (=conf.yml)
        """
        assert sid in self._sessions
        d = self._sessions[sid].config
        d["runtime"]["plugin"] = ""
        return d

    def single_session_status(
        self, sid: str, unsafe_status_filter: str | None = None
    ) -> dict[str, list[str]] | list[str]:
        """
        Get per-session status infos

        :param sid: Session id to extract info from.
        :param unsafe_status_filter: optional status to filter in, defaults to None

            .. warning::
                Security: unsafe_status_filter is provided from webview user !

        :return: A dict of statuses (or a single list if the filter is used)
        """
        assert sid in self._sessions
        statuses = self._sessions[sid].results.status_view
        if unsafe_status_filter:
            assert unsafe_status_filter in statuses
            status = statuses[unsafe_status_filter]
            assert isinstance(status, list)
            return status
        return statuses

    def single_session_tags(self, sid: str) -> dict[str, dict]:
        """
        Get per-session available tags.

        Outputs a per-status dict.

        :param sid: Session ID
        :return: dict of statuses
        """
        assert sid in self._sessions
        return self._sessions[sid].results.tags_view

    def single_session_job_cnt(self, sid: str) -> int:
        """
        Get per session number of job.

        :param sid: the session ID
        :return: The number of jobs (total)
        """
        assert sid in self._sessions
        return self._sessions[sid].results.total_cnt

    def single_session_labels(self, sid: str) -> dict[str, dict]:
        """
        Get per-session available labels.

        Outputs a per-status dict.

        :param sid: Session ID
        :return: dict of statuses
        """
        assert sid in self._sessions
        labels_info = self._sessions[sid].results.tree_view
        return {
            label: labels_info[label]
            for label in self._sessions[sid].config["validation"]["dirs"].keys()
        }

    def single_session_build_path(self, sid: str) -> str:
        """
        Get build prefix of a given session.

        :param sid: session ID
        :return: build path
        """
        assert sid in self._sessions
        return self._sessions[sid].prefix

    def single_session_map_id(self, sid: str, jid: str) -> Test | None:
        """
        For a given session id, convert a job it into its relative class:`Test` object.

        :param sid: Session ID
        :param jid: Job ID
        :return: the Actual test object
        """
        assert sid in self._sessions
        return self._sessions[sid].results.map_id(jid)

    def single_session_get_view(
        self, sid: str, name: str, unsafe_subset: str | None = None, summary: bool = False
    ) -> dict[str, dict] | None:
        """
        Get a specific view from a given session.

        A view consists in a per-status split of jobs depending on the purpose
        of the stored view. PCVS currently provide automatically:
        * Per status
        * Per tags
        * Per labels

        If `subset` is provided, only the nodes matching the key will be
        returned.
        If `summary` is True, a job count will be returned instead of actual
        job ids.

        :param sid: Session ID
        :param name: view name
        :param unsafe_subset: only a selection of the view, defaults to None

            .. warning::
                Security: unsafe_subset is provided from webview user !

        :param summary: Should it be summarized, defaults to False
        :return: the result dict
        """
        if sid not in self._sessions:
            return None

        d = {}
        if name == "tags":
            d = self.single_session_tags(sid)
        elif name == "labels":
            d = self.single_session_labels(sid)
        else:
            return None

        if unsafe_subset is not None:
            d = {k: v for k, v in d.items() if unsafe_subset in k}

        if d and summary:
            return {k: self.dict_convert_list_to_cnt(v) for k, v in d.items()}
        return d


def upload_buildir_results(
    data_manager: Report, buildir: str  # pylint: disable=unused-argument
) -> None:
    """Upload a whole test-suite from disk to the server data model.

    :param data_manager: The report data manager.
    :param buildir: the build directory.
    """
    # TODO: That would be cool to dev the real stuff,
    # before making interface that use function that never existed.

    # first, need to determine the session ID -> conf.yml
    # with open(os.path.join(buildir, "conf.yml"), "r", encoding="utf-8") as fh:
    #     conf_yml = YAML().load(fh)

    # sid = conf_yml["validation"]["sid"]
    # dataman = data_manager

    # man = BuildDirectoryManager(buildir)
    # dataman.insert_session(
    #    sid,
    #    {
    #        "buildpath": buildir,
    #        "state": Session.State.COMPLETED,
    #        "dirs": conf_yml["validation"]["dirs"],
    #    },
    # )
    # for test in man.results.browse_tests():
    #    # FIXME: this function does not exist any more
    #    # man.save(test)
    #    dataman.insert_test(sid, test)

    # dataman.close_session(sid, {"state": Session.State.COMPLETED})
