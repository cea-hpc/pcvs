from multiprocessing import Process
import subprocess
from datetime import datetime

import os
import sys
import fcntl
import yaml
import time

from pcvs.helpers import system, log
from pcvs import PATH_SESSION, PATH_SESSION_LOCKFILE


def unlock_session_file():
    with open(PATH_SESSION_LOCKFILE, "w+") as fh:
        fcntl.flock(fh, fcntl.LOCK_UN)

def lock_session_file():
    locked = False
    with open(PATH_SESSION_LOCKFILE, "w+") as fh:
        while not locked:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError:
                time.sleep(1)


def store_session_to_file(c):
    all_sessions = None
    sid = 0
    
    lock_session_file()
    
    if os.path.isfile(PATH_SESSION):
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    
    if all_sessions is not None:
        sid = max(all_sessions.keys()) + 1
    else:
        #yaml.safe_load returns None if empty
        all_sessions = dict()
        
    assert(sid not in all_sessions.keys())
    all_sessions[sid] = c
    with open(PATH_SESSION, 'w') as fh:
        yaml.safe_dump(all_sessions, fh)

    unlock_session_file()
    return sid


def update_session_from_file(sid, update):
    lock_session_file()
    all_sessions = None
    if os.path.isfile(PATH_SESSION):
        with open(PATH_SESSION, 'r') as fh:
            all_sessions = yaml.safe_load(fh)
    
    if all_sessions is not None and sid in all_sessions:
        for k, v in update.items():
            all_sessions[sid][k] = v
        with open(PATH_SESSION, 'w') as fh:
            yaml.safe_dump(all_sessions, fh)

    
def remove_session_from_file(sid):
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
            #else, truncate the file to zero

    unlock_session_file()


def list_alive_sessions():
    lock_session_file()
    with open(PATH_SESSION, 'r') as fh:
        all_sessions = yaml.safe_load(fh)
    unlock_session_file()
    return all_sessions


def main_detached_session(sid, user_func, io_file, *args, **kwargs):
    if os.fork() != 0:
        return

    ret = 0

    if io_file:
        sys.stdout = open(io_file, 'w')
        sys.stderr = sys.stdout
    
    try:
        ret = user_func(*args, **kwargs)
    finally:
        if io_file:
            sys.stdout.close()
        update_session_from_file(sid, {
            'state': Session.STATE_COMPLETED,
            'ended': datetime.now()
        })
    
    return ret


class Session:
    STATE_IN_PROGRESS = 0
    STATE_COMPLETED = 1
    STATE_ERROR = 2

    __state_str = None

    @property
    def state(self):
        return self._session_infos['state']

    @property
    def id(self):
        return self._sid

    @property
    def str_state(self):
        # init default at first call
        # as utf codes are determined at runtime
        if self.__state_str is None:
            self.__state_str = {
                self.STATE_IN_PROGRESS: "IN_PROGRESS",
                self.STATE_COMPLETED: "COMPLETED",
                self.STATE_ERROR: "ERROR"
            }
        return self.__state_str[self._sid]

    def property(self, kw):
        assert(kw in self._session_infos)
        return self._session_infos[kw]

    def __init__(self, date=datetime.now(), path="."):
        self._func = None
        self._sid = -1
        self._session_infos = {
            "path": path,
            "io": None,
            "state": self.STATE_IN_PROGRESS,
            "started": date,
            "ended": None
        }
    
    def load_from(self, sid, data):
        self._sid = sid
        self._session_infos = data

    def register_callback(self, callback, io_file=None):
        self._func = callback
        self.register_io_file(io_file)

    def register_io_file(self, pathfile=None):
        self._session_infos['io'] = pathfile
        self._io_file = pathfile

    def run_detached(self, *args, **kwargs):
        if self._func is not None:
            self._sid = store_session_to_file(self._session_infos)
            
            child = Process(target=main_detached_session,
                            args=(self._sid, self._func, self._io_file, *args),
                            kwargs=kwargs,
                            daemon=True)
            child.start()
            child.join()
            return self._sid

    def run(self, *args, **kwargs):
        if self._func is not None:
            self._sid = store_session_to_file(self._session_infos)

            # save stdout/stder to out.log & keep it interactive
            # to be replaced with new I/O interface
            t = subprocess.Popen(["tee", self._io_file],
                                    stdin=subprocess.PIPE)
            os.dup2(t.stdin.fileno(), sys.stdout.fileno())
            os.dup2(t.stdin.fileno(), sys.stderr.fileno())
            
            # run the code
            self._func(*args, **kwargs)

            remove_session_from_file(self._sid)

    def attach(self, sid):
        pass