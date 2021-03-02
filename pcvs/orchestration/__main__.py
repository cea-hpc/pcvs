
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


class Task(threading.Thread):
    def __init__(self, job):
        self._job = job
        threading.Thread.__init__(self)

    def run(self):
        p = subprocess.Popen('{}'.format(self._job.command),
                        shell=True,
                        stderr=subprocess.STDOUT,
                        stdout=subprocess.PIPE)
        
l = list()
for i in range(0, 100):
    j = Job()
    l.append(j)
    j.start()


for elt in l:
    elt.join()
