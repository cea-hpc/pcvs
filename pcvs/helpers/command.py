import subprocess

from pcvs.helpers import log


class Command:
    def __init__(self, cmd, env=None, shell=False):
        self._cmd = cmd
        self._env = env
        self._out = None
        self._err = None
        self._sh = shell
    
    def run(self):
        log.err('loo')
        try:
            r = subprocess.check_call(
                    self._cmd,
                    shell=self._sh,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            self._out = r.stdout
            self._err = r.stderr
        except subprocess.CalledProcessError as e:
            log.err("Command err", '{}'.format(e))

    
    @property
    def stderr(self):
        return self._err

    @property
    def stdout(self):
        return self._out

    def __str__(self):
        return self._cmd


class CommandChain:
    def __init(self, list_of_commands):
        self._cmds = [Command(d) for d in list_of_commands]

    def build(self, shell=True):
        if shell is True:
            return " && ".join([str(c) for c in self._cmds])
        else:
            for d in self._cmds:
                yield d
    
    def run(self, out=True):
        try:
            ret = subprocess.check_output(
                    self.build(shell=True),
                    shell=True
                )
        except subprocess.CalledProcessError as e:
            log.err(e)
            ret = None
    
        return ret
