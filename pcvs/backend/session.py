from multiprocessing import Process
import subprocess

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
    lock_session_file()
    with open(PATH_SESSION, 'r') as fh:
        all_sessions = yaml.safe_load(fh)
        sid = 0
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

def remove_session_from_file(sid):
    lock_session_file()
    with open(PATH_SESSION, 'r') as fh:
        all_sessions = yaml.safe_load(fh)
        assert(sid in all_sessions)
    
    del all_sessions[sid]
    
    with open(PATH_SESSION, 'w') as fh:
        yaml.safe_dump(all_sessions, fh)

    unlock_session_file()



def list_alive_sessions():
    with open(PATH_SESSION, 'r') as fh:
        all_sessions = yaml.safe_load(fh)

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
        remove_session_from_file(sid)
    
    return ret


class Session:
    STATE_IN_PROGRESS = 0
    STATE_COMPLETED = 1
    STATE_ERROR = 2

    __state_str = {
        STATE_IN_PROGRESS: "IN_PROGRESS {}".format(log.utf("spin")),
        STATE_COMPLETED: "COMPLETED {}".format(log.utf("succ")),
        STATE_ERROR: "ERROR {}".format(log.utf("fail"))
    }

    @classmethod
    def str_state(cls, state_code):
        return cls.__state_str[state_code]

    def __init__(self):
        self._func = None
        self._session_infos = {
            "path": None,
            "io": None,
            "state": self.STATE_IN_PROGRESS,
        }

    def register_callback(self, callback, io_file=None):
        self._func = callback
        self.register_io_file(io_file)

    def register_io_file(self, pathfile=None):
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
            log.print_item("Session {} started, use `pcvs session` to interact.".format(self._sid))

        
    def run(self, *args, **kwargs):
        if self._func is not None:
                # save stdout/stder to out.log & keep it interactive
                t = subprocess.Popen(["tee", self._io_file],
                                     stdin=subprocess.PIPE)
                os.dup2(t.stdin.fileno(), sys.stdout.fileno())
                os.dup2(t.stdin.fileno(), sys.stderr.fileno())
                
                # run the code
                self._func(*args, **kwargs)

    def attach(self, sid):
        pass