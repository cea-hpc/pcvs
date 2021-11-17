import copy
import os
from datetime import datetime
from enum import IntEnum
from multiprocessing import Process

from ruamel.yaml import YAML
from ruamel.yaml.main import yaml_object

from pcvs import PATH_SESSION
from pcvs.helpers import log, utils

yml = YAML()


def unlock_session_file():
    """Release the lock after manipulating the session.yml file.

    The call won't fail if the lockfile is not taken before unlocking.
    """
    utils.unlock_file(PATH_SESSION)


def lock_session_file(timeout=None):
    """Acquire the lockfil before manipulating the session.yml file.

    This ensure safety between multiple PCVS instances. Be sure to call
    `unlock_session_file()` once completed

    :param timeout: return from blocking once timeout is expired (raising
        TimeoutError)
    :type timeout: int
    """
    utils.lock_file(PATH_SESSION, timeout=timeout)


def store_session_to_file(c):
    """Save a new session into the session file (in HOME dir).

    :param c: session infos to store
    :type c: dict
    :return: the sid associated to new create session id.
    :rtype: int
    """
    all_sessions = None
    sid = -1
    global yml

    lock_session_file()
    try:
        # to operate, PCVS needs to full-read and then full-write the whole file
        if os.path.isfile(PATH_SESSION):
            with open(PATH_SESSION, 'r') as fh:
                all_sessions = yml.load(fh)

        # compute the session id, incrementally done from the highest session id
        # currently running and registered.
        # Please not a session is not flushed away from logs until the user
        # explicitly does it
        if all_sessions is None:
            all_sessions = {"__metadata": {"next": 0}}

        # Lookup for an available session id number
        sid = all_sessions["__metadata"]["next"]
        while sid in all_sessions.keys() or sid == -1:
            sid += 1

        all_sessions["__metadata"]["next"] = (sid + 1) % 1000000

        assert(sid not in all_sessions.keys())
        all_sessions[sid] = c

        # dump the file back
        with open(PATH_SESSION, 'w') as fh:
            yml.dump(all_sessions, fh)
    finally:
        unlock_session_file()
    return sid


def update_session_from_file(sid, update):
    """Update data from a running session from the global file.

    This only add/replace keys present in argument dict. Other keys remain.

    :param sid: the session id
    :type sid: int
    :param update: the keys to update. If already existing, content is replaced
    :type: dict
    """
    global yml
    lock_session_file()
    try:
        all_sessions = None
        if os.path.isfile(PATH_SESSION):
            with open(PATH_SESSION, 'r') as fh:
                all_sessions = yml.load(fh)

        if all_sessions is not None and sid in all_sessions:
            for k, v in update.items():
                all_sessions[sid][k] = v
            # only if editing is done, flush the file back
            with open(PATH_SESSION, 'w') as fh:
                yml.dump(all_sessions, fh)
    finally:
        unlock_session_file()


def remove_session_from_file(sid):
    """clear a session from logs.

    :param sid: the session id to remove.
    :type sid: int
    """
    global yml
    lock_session_file()
    try:
        all_sessions = None
        if os.path.isfile(PATH_SESSION):
            with open(PATH_SESSION, 'r') as fh:
                all_sessions = yml.load(fh)

        if all_sessions is not None and sid in all_sessions:
            del all_sessions[sid]
            with open(PATH_SESSION, 'w') as fh:
                if len(all_sessions) > 0:
                    yml.dump(all_sessions, fh)
                # else, truncate the file to zero -> open(w) with no data
    finally:
        unlock_session_file()


def list_alive_sessions():
    """Load and return the complete dict from session.yml file

    :return: the session dict
    :rtype: dict
    """
    global yml
    lock_session_file(timeout=15)

    try:
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yml.load(fh)
            if all_sessions:
                del all_sessions["__metadata"]
    except FileNotFoundError as e:
        all_sessions = {}
    finally:
        unlock_session_file()
    return all_sessions


def main_detached_session(sid, user_func, *args, **kwargs):
    """Main function processed when running in detached mode.

    This function is called by Session.run_detached() and is launched from
    cloned process (same global env, new main function).

    :raises Exception: any error occuring during the main process is re-raised.

    :param sid: the session id
    :param user_func: the Python function used as the new main()
    :param args: user_func() arguments
    :type args: tuple
    :param kwargs: user_func() arguments
    :type kwargs: dict
    """

    # When calling a subprocess, the parent is attached to its child
    # Parent won't terminate if a single child is still running.
    # Setting a child 'deamon' will allow parent to terminate children at exit
    # (still not what we want)
    # the trick is to double fork: the parent creates a child, also crating a
    # a child (child2). When the process is run, the first child completes
    # immediately, relasing the parent.
    if os.fork() != 0:
        return

    ret = 0

    try:
        # run the code in detached mode
        # beware: this function should only raises exception to stop.
        # a sys.exit() will bypass the rest here.
        ret = user_func(*args, **kwargs)
        update_session_from_file(sid, {
            'state': Session.State.COMPLETED,
            'ended': datetime.now()
        })
    except Exception as e:
        update_session_from_file(sid, {
            'state': Session.State.ERROR,
            'ended': datetime.now()
        })
        raise e

    return ret


class Session:
    """Object representing a running validation (detached or not).

    Despite the fact it is designed for manage concurrent runs,  it takes a
    callback and can be derived for other needs.

    :param _func: user function to be called once the session starts 
    :type _func: Callable
    :param _sid: session id, automatically generated
    :type _sid: int
    :param _session_infos: session infos dict
    :type _session_infos: dict

    """
    @yaml_object(yml)
    class State(IntEnum):
        """Enum of possible Session states."""
        WAITING = 0
        IN_PROGRESS = 1
        COMPLETED = 2
        ERROR = 3

        @classmethod
        def to_yaml(cls, representer, data):
            """Convert a Test.State to a valid YAML representation.

            A new tag is created: 'Session.State' as a scalar (str).
            :param dumper: the YAML dumper object 
            :type dumper: :class:`YAML().dumper`
            :param data: the object to represent
            :type data: class:`Session.State`
            :return: the YAML representation
            :rtype: Any
            """
            return representer.represent_scalar(u'!State', u'{}||{}'.format(data.name, data.value))

        @classmethod
        def from_yaml(cls, constructor, node):
            """Construct a :class:`Session.State` from its YAML representation.

            Relies on the fact the node contains a 'Session.State' tag.
            :param loader: the YAML loader
            :type loader: :class:`yaml.FullLoader`
            :param node: the YAML representation
            :type node: Any
            :return: The session State as an object
            :rtype: :class:`Session.State`
            """
            s = constructor.construct_scalar(node)
            name, value = s.split('||')
            obj = Session.State(int(value))
            assert(obj.name == name)

            return obj

        def __str__(self):
            """Stringify the state.

            :return: the enum name.
            :rtype: str
            """
            return self.name

    @property
    def state(self):
        """Getter to session status.

        :return: session status
        :rtype: int
        """
        return self._session_infos['state']

    @property
    def id(self):
        """Getter to session id.

        :return: session id
        :rtype: int
        """
        return self._sid

    @property
    def rc(self):
        """Gett to final RC.

        :return: rc
        :rtype: int
        """
        return self._rc

    @property
    def infos(self):
        """Getter to session infos.

        :return: session infos
        :rtype: dict
        """
        return self._session_infos

    def property(self, kw):
        """Access specific data from the session stored info session.yml.

        :param kw: the information to retrieve. kw must be a valid key
        :type kw: str
        :return: the requested session infos if exist
        :rtype: Any
        """
        assert(kw in self._session_infos)
        return self._session_infos[kw]

    def __init__(self, date=None, path="."):
        """constructor method.

        :param date: the start timestamp
        :type date: datetime.datetime
        :param path: the build directory
        :type path: str
        """
        self._func = None
        self._rc = -1
        self._sid = -1
        # this dict is then flushed to the session.yml
        self._session_infos = {
            "path": path,
            "io": None,
            "progress": 0,
            "state": Session.State.WAITING,
            "started": date,
            "ended": None
        }

    def load_from(self, sid, data):
        """Update the current object with session infos read from global file.

        :param sid: session id read from file
        :type sid: int
        :param data: session infos read from file
        :type data: dict
        """
        self._sid = sid
        self._session_infos = data

    def register_callback(self, callback, io_file=None):
        """Register the callback used as main function once the session is
        started.

        :param callback: function to invoke
        :type callback: Callable
        :param io_file: Where I/O will be redirected once session is started
        :type io_file: str, optional
        """
        self._func = callback
        self.register_io_file(io_file)

    def register_io_file(self, pathfile=None):
        """Register the I/O file when stdout/stderr will be flushed once the
        session is started.

        :param pathfile: the path to redirect I/Os, may be None
        :type pathfile: str, optional
        """
        self._session_infos['io'] = pathfile
        self._io_file = pathfile

    def run_detached(self, *args, **kwargs):
        """Run the session is detached mode.

        Arguments are for user function only.
        :param args: user function positional arguments
        :type args: tuple
        :param kwargs user function keyword-based arguments.
        :type kwargs: tuple

        :return: the Session id created for this run.
        :rtype: int
        """
        if self._func is not None:
            # some sessions can have their starting time set directly when
            # initializing the object.
            # for instance for runs, elapsed time not session time but wall time"""
            if self.property('started') == None:
                self._session_infos['started'] = datetime.now()

            # flag it as running & make the info public
            self._session_infos['state'] = self.State.IN_PROGRESS
            self._sid = store_session_to_file(self._session_infos)

            # run the new process
            child = Process(target=main_detached_session,
                            args=(self._sid, self._func, *args),
                            kwargs=kwargs)

            # set the child IOManager before starting
            # enable logfile but disable tty
            # save the old manager to restore it after child starts
            old = copy.copy(log.manager)
            log.manager.set_logfile(enable=True, logfile=self._io_file)
            log.manager.set_tty(enable=False)
            child.start()
            # complete the first child, to allow this process to terminate
            child.join()

            # do not close tty, to extra info to be printed but not logged
            log.manager = old
            log.manager.set_logfile(enable=False)

            return self._sid

    def run(self, *args, **kwargs):
        """Run the session normally, without detaching the focus.

        Arguments are user function ones. This function is also in charge of
        redirecting I/O properly (stdout, file, logs)

        :param args: user function positional arguments
        :type args: tuple
        :param kwargs user function keyword-based arguments.
        :type kwargs: tuple
        """
        if self._func is not None:
            # same as above, shifted starting time or not
            if self.property('started') == None:
                self._session_infos['started'] = datetime.now()

            self._session_infos['state'] = self.State.IN_PROGRESS
            self._sid = store_session_to_file(self._session_infos)

            log.manager.set_logfile(enable=True, logfile=self._io_file)
            log.manager.set_tty(enable=True)
            # run the code
            try:
                self._rc = self._func(*args, **kwargs)
            finally:
                # in that mode, no information is left to users once the session
                # is complete.
                remove_session_from_file(self._sid)

        return self._sid
