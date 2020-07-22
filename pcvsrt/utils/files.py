import os
import subprocess
from contextlib import contextmanager

@contextmanager
def cwd(path):
    if not os.path.isdir(path):
        os.mkdir(path)
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)

def open_in_editor(path, e=None):
    editor = e if e is not None else os.environ['EDITOR']
    subprocess.run([editor, path])

class FileManager:
    """Manage a file from PCVS scope.

    This class may not differ so much from the builtins
    """
    def __init__(self, filepath, mode):
        self._filepath = filepath
        self._mode = mode
        self._fd = open(filepath, mode)

    def read(self):
        self._fd.read()

    def write(self, string):
        self._fd.write(string)

    def __del__(self):
        self._fd.close()
