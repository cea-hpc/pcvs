import os
from filelock import FileLock


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


class LockFileManager(FileManager):
    """Manage a file against concurrent accessses.
    """
    def __init__(self, filepath, mode):
        self._filelock = os.path.join(".", os.path.basename(filepath), ".lock")
        self._lock = FileLock(self._lock, timeout=1)
        self._lock.acquire()
        FileManager.__init__(self, filepath, mode)

    def edit(self):
        os.system('{} {}'.format(os.getenv('EDITOR'), self._filepath))
        self.__init__(self._filepath, self._mode)

    def __fini__(self):
        FileManager.__del__(self)
        self._lock.release()
