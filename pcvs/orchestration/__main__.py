
import threading
import subprocess

class Job:
    def __init__(self):
        self._command = "echo 'hello'"
        self._success = False
    
    @property
    def command(self):
        return self._command

    @property
    def success(self):
        return self._success
    
    def update_after_exec(self, rc=0, out=""):
        pass