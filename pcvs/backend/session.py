import copy
import fcntl
import os
import time
from datetime import datetime
from multiprocessing import Process

import yaml

from pcvs import PATH_SESSION, PATH_SESSION_LOCKFILE
from pcvs.helpers import log, utils


def unlock_session_file():
    """ Release the lock after manipulating the session.yml file.
        The call won't failed if the lockfile is not taken before unlocking.
    """
    utils.unlock_file(PATH_SESSION_LOCKFILE)
    
def lock_session_file(timeout=None):
    """Acquire the lockfil before manipulating the session.yml file.
        This ensure safety between multiple PCVS instances.
        Be sure to call `unlock_session_file()` once completed
    """
    utils.lock_file(PATH_SESSION_LOCKFILE, timeout=timeout)


def store_session_to_file(c):
    """Save a new session into the session file (in HOME dir).
        The argument is the content to save for this session (dict)
    """
    all_sessions = None
    sid = 0
    
    lock_session_file()
    # to operate, PCVS needs to full-read and then full-write the whole file
    if os.path.isfile(PATH_SESSION):
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    
    # compute the session id, incrementally done from the highest session id
    # currently running and registered.
    # Please not a session is not flushed away from logs until the user
    # explicitly does it
    if all_sessions is not None:
        sid = max(all_sessions.keys()) + 1
    else:
        #yaml.safe_load returns None if empty
        all_sessions = dict()
    
    assert(sid not in all_sessions.keys())
    all_sessions[sid] = c

    # dump the file back
    with open(PATH_SESSION, 'w') as fh:
        yaml.safe_dump(all_sessions, fh)

    unlock_session_file()
    return sid


def update_session_from_file(sid, update):
    """ Update data from a running session from the global file
        The argument are:
        - sid: the session id
        - update: the keys to update. If already existing, content is replaced
    """

    lock_session_file()
    all_sessions = None
    if os.path.isfile(PATH_SESSION):
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    
    
    if all_sessions is not None and sid in all_sessions:
        for k, v in update.items():
            all_sessions[sid][k] = v
        # only if editing is done, flush the file back
        with open(PATH_SESSION, 'w') as fh:
            yaml.safe_dump(all_sessions, fh)

    unlock_session_file()

    
def remove_session_from_file(sid):
    """clear a session from logs. Argument is the session id"""
    lock_session_file()
    all_sessions = None
    if os.path.isfile(PATH_SESSION):
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    
    if all_sessions is not None and sid in all_sessions:
        del all_sessions[sid]
        with open(PATH_SESSION, 'w') as fh:
            if len(all_sessions) > 0:
                yaml.safe_dump(all_sessions, fh)
            #else, truncate the file to zero -> open(w) with no data

    unlock_session_file()


def list_alive_sessions():
    """load and return the complete dict from session.yml file"""
    lock_session_file(timeout=15)

    try:
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    except FileNotFoundError as e:
        all_sessions = {}

    unlock_session_file()
    return all_sessions


def main_detached_session(sid, user_func, *args, **kwargs):
    """Main function processed when running in detached mode. This function
    is called by Session.run_detached() and is launched from cloned process
    (same global env, new main function). Arguments are:
        - sid: the session id
        - user_func: the Python fonction used as the new main()
        - *args, **kwargs: user_func() arguments
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
            'state': Session.STATE_COMPLETED,
            'ended': datetime.now()
        })
    except Exception as e:
        update_session_from_file(sid, {
            'state': Session.STATE_ERROR,
            'ended': datetime.now()
        })
        raise e
        
    return ret


class Session:
    """Object representing a running validation (detached or not). Despite the
    fact it is designed for manage concurrent runs,  it takes a callback and
    can be derived for other needs.
    """
    STATE_WAITING = -1
    STATE_IN_PROGRESS = 0
    STATE_COMPLETED = 1
    STATE_ERROR = 2
    
    __state_str = {
        STATE_IN_PROGRESS: "IN_PROGRESS",
        STATE_COMPLETED: "COMPLETED",
        STATE_ERROR: "ERROR",
        STATE_WAITING: "WAITING"
    }

    @property
    def state(self):
        return self._session_infos['state']

    @property
    def id(self):
        return self._sid
    @property
    def infos(self):
        return self._session_infos

    @property
    def str_state(self):
        return self.__state_str[self._sid]

    def property(self, kw):
        """Access specific data from the session stored info session.yml"""
        assert(kw in self._session_infos)
        return self._session_infos[kw]

    def __init__(self, date=None, path="."):
        self._func = None
        self._sid = -1
        # this dict is then flushed to the session.yml
        self._session_infos = {
            "path": path,
            "io": None,
            "state": self.STATE_WAITING,
            "started": date,
            "ended": None
        }
    
    def load_from(self, sid, data):
        """Function used to update the current object with session infos
        read from global file
        """
        self._sid = sid
        self._session_infos = data

    def register_callback(self, callback, io_file=None):
        """Register the callback used as main function once the sessio
            is started
        """
        self._func = callback
        self.register_io_file(io_file)

    def register_io_file(self, pathfile=None):
        """Register the I/O file when stdout/stderr will be flushed once
            the session is started.
        """
        self._session_infos['io'] = pathfile
        self._io_file = pathfile

    def run_detached(self, *args, **kwargs):
        """Run the session is detached mode. Arguments are for user function
        only"""
        if self._func is not None:
            # some sessions can have their starting time set directly when
            # initializing the object.
            # for instance for runs, elapsed time not session time but wall time"""
            if self.property('started') == None:
                self._session_infos['started'] = datetime.now()
            
            #flag it as running & make the info public
            self._session_infos['state'] = self.STATE_IN_PROGRESS
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
        """Run the session normally, without detaching the focus. Arguments are
            user function ones. This function is also in charge of redirecting
            I/O properly (stdout, file, logs)
        """
        if self._func is not None:
            # same as above, shifted starting time or not
            if self.property('started') == None:
                self._session_infos['started'] = datetime.now()
            self._session_infos['state'] = self.STATE_IN_PROGRESS
            self._sid = store_session_to_file(self._session_infos)

            log.manager.set_logfile(enable=True, logfile=self._io_file)
            log.manager.set_tty(enable=True)
            # run the code
            try:
                self._func(*args, **kwargs)
            finally:
                # in that mode, no information is left to users once the session
                # is complete.
                remove_session_from_file(self._sid)
