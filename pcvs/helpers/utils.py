import os
import shutil
import signal
import time
from contextlib import contextmanager
from shutil import SameFileError

from pcvs import (NAME_BUILDFILE, NAME_BUILDIR, NAME_SRCDIR, PATH_HOMEDIR,
                  PATH_INSTDIR)
from pcvs.helpers import log
from pcvs.helpers.exceptions import (CommonException, LockException,
                                     RunException)
from pcvs.helpers.system import MetaConfig

####################################
##    STORAGE SCOPE MANAGEMENT    ##
####################################
STORAGES = {
    'global': PATH_INSTDIR,
    'user': PATH_HOMEDIR,
    'local': os.path.join(os.getcwd(), NAME_SRCDIR)
}


def create_home_dir():
    """Create a home directory
    """
    if not os.path.exists(PATH_HOMEDIR):
        os.makedirs(PATH_HOMEDIR)


def storage_order():
    """Return scopes in order of searching.

    :return: a list of scopes
    :rtype: list
    """
    return ['local', 'user', 'global']


def check_valid_scope(s):
    """Check if argument is a valid scope (local, user, global).

    :param s: scope to check
    :type s: str
    :raises CommonException.BadTokenError: the argument is not a valid scope
    """
    if s not in storage_order() and s is not None:
        raise CommonException.BadTokenError(s)


def extract_infos_from_token(s, pair="right", single="right", maxsplit=3):
    """Extract fields from tokens (a, b, c) from user's string.

    :param s: the input string
    :type s: str
    :param pair: padding side when only 2 tokens found, defaults to "right"
    :type pair: str, optional
    :param single: padding side when only 1 token found, defaults to "right"
    :type single: str, optional
    :param maxsplit: maximum split number for s, defaults to 3
    :type maxsplit: int, optional
    :return: 3-string-tuple: mapping (scope, kind, name), any of them may be null
    :rtype: tuple
    """

    array = s.split(".")
    if len(array) >= maxsplit:
        return (array[0], array[1], ".".join(array[maxsplit-1:]))
    elif len(array) == 2:
        # two cases: a.b or b.c
        if pair == 'left':
            return (array[0], array[1], None)
        elif pair == 'span':
            return (array[0], None, array[1])
        else:
            return (None, array[0], array[1])
    elif len(array) == 1:
        if single == "left":  # pragma: no cover
            return (s, None, None)
        elif single == "center":
            return (None, s, None)
        else:
            return (None, None, s)
    else:  # pragma: no cover
        pass
    return (None, None, None)  # pragma: no cover


def __determine_local_prefix(path, prefix):
    """Search for the ``local`` storage in the current (or parent) directory.

    :param path: ``local`` storage
    :type path: os.path, str
    :param prefix: prefix for ``local`` storage
    :type prefix: os.path, str
    :return: complete path to ``local`` storage
    :rtype: os.path, str
    """
    cur = path
    parent = "/"
    while not os.path.isdir(os.path.join(cur, prefix)):
        parent = os.path.dirname(cur)
        # Reach '/' and not found
        if parent == cur:
            cur = path
            break
        # else, look for parent
        cur = parent

    return os.path.join(cur, prefix)


def set_local_path(path):
    """Set the prefix for the ``local`` storage.

    :param path: path of the ``local`` storage
    :type path: os.path
    """
    assert (os.path.isdir(path))
    found = __determine_local_prefix(path, NAME_SRCDIR)

    # if local is the same as user path, discard
    if found in STORAGES.values():
        found = os.path.join(path, NAME_SRCDIR)
    STORAGES['local'] = found

####################################
####     PATH MANIPULATION      ####
####################################


def create_or_clean_path(prefix, dir=False):
    """Create a path or cleans it if it already exists.

    :param prefix: prefix of the path to create
    :type prefix: os.path, str
    :param dir: True if the path is a directory, defaults to False
    :type dir: bool, optional
    """
    if not os.path.exists(prefix):
        if dir:
            os.mkdir(prefix)
        else:
            assert(os.path.isdir(os.path.dirname(prefix)))
            open(prefix, 'w+').close()
        return

    # else, a previous path exists
    if os.path.isdir(prefix):
        shutil.rmtree(prefix)
        os.mkdir(prefix)
    elif os.path.isfile(prefix):
        os.remove(prefix)


@contextmanager
def cwd(path):
    """Change the working directory.

    :param path: new working directory
    :type path: os.path, str
    """
    if not os.path.isdir(path):
        os.mkdir(path)
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


def copy_file(src, dest):
    """Copy a source file into a destination directory.

    :param src: source file to copy.
    :type src: str
    :param dest: destination directory, may not exist yet.
    :type dest: str
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        shutil.copy(src, dest)
    except SameFileError:
        pass

####################################
####           MISC.            ####
####################################


def generate_local_variables(label, subprefix):
    """Return directories from PCVS working tree :

        - the base source directory
        - the current source directory
        - the base build directory
        - the current build directory

    :param label: name of the object used to generate paths
    :type label: str
    :param subprefix: path to the subdirectories in the base path
    :type subprefix: str
    :raises CommonException.NotFoundError: the label is not recognized as to be
        validated
    :return: paths for PCVS working tree
    :rtype: tuple
    """
    if label not in MetaConfig.root.validation.dirs:
        raise CommonException.NotFoundError(label)

    if subprefix is None:
        subprefix = ""

    base_srcdir = MetaConfig.root.validation.dirs[label]
    cur_srcdir = os.path.join(base_srcdir, subprefix)
    base_buildir = os.path.join(
        MetaConfig.root.validation.output, "test_suite", label)
    cur_buildir = os.path.join(base_buildir, subprefix)

    return base_srcdir, cur_srcdir, base_buildir, cur_buildir


def check_valid_program(p, succ=None, fail=None, raise_if_fail=True):
    """Check if p is a valid program, using the ``which`` function.

    :param p: program to check
    :type p: str
    :param succ: function to call in case of success, defaults to None
    :type succ: optional
    :param fail: function to call in case of failure, defaults to None
    :type fail: optional
    :param raise_if_fail: Raise an exception in case of failure, defaults to True
    :type raise_if_fail: bool, optional
    :raises RunException.ProgramError: p is not a valid program
    :return: True if p is a program, False otherwise
    :rtype: bool
    """
    if not p:
        return
    try:
        filepath = shutil.which(p)
        res = os.access(filepath, mode=os.X_OK)
    except TypeError:  # which() can return None
        res = False

    if res is True and succ is not None:
        succ("'{}' found at '{}'".format(os.path.basename(p), filepath))

    if res is False:
        if fail is not None:
            fail("{} not found or not an executable".format(p))
        if raise_if_fail:
            raise RunException.ProgramError(p)

    return res


def find_buildir_from_prefix(path):
    """Find the build directory from the ``path`` prefix.

    :param path: path to search the build directory from
    :type path: os.path, str
    :raises CommonException.NotFoundError: the build directory is not found
    :return: the path of the build directory
    :rtype: os.path
    """
    # three scenarios:
    # - path = $PREFIX (being a buildir) -> use as build dir
    # - path = $PREFIX (containing a buildir) - > join(.pcvs-build)
    # - otherwise, raise a path error
    if not os.path.isfile(os.path.join(path, NAME_BUILDFILE)):
        path = os.path.join(path, NAME_BUILDIR)
        if not os.path.isfile(os.path.join(path, NAME_BUILDFILE)):
            raise CommonException.NotFoundError("build-dir in {}".format(path))
    return path


def get_lockfile_name(f):
    """From a file to mutex, return the file lock name associated with it.

    For instance for /a/b.yml, the lock file name will be /a/.b.yml.lck

    :param f: the file to mutex
    :type f: str
    """
    path = os.path.dirname(f)
    filename = os.path.basename(f)

    # hide lock file if original file isn't
    if not filename.startswith("."):
        filename = "." + filename

    return os.path.join(path, filename + ".lck")


def unlock_file(f):
    """Remove lock from a directory.

    :param f: file locking the directory
    :type f: os.path
    """
    lf_name = get_lockfile_name(f)
    if os.path.exists(lf_name) and os.path.isfile(lf_name):
        os.remove(lf_name)
        log.manager.debug("Unlock {}".format(lf_name))


def lock_file(f, reentrant=False, timeout=None, force=True):
    """Try to lock a directory.

    :param f: name of lock
    :type f: os.path
    :param reentrant: True if this process may have locked this file before,
        defaults to False
    :type reentrant: bool, optional
    :param timeout: time before timeout, defaults to None
    :type timeout: int (seconds), optional
    :raises LockException.TimeoutError: timeout is reached before the directory
        is locked
    :return: True if the file is reached, False otherwise
    :rtype: bool
    """

    log.manager.debug("Attempt locking {}".format(f))
    if force:
        unlock_file(f)
    locked = trylock_file(f, reentrant)
    count = 0
    while not locked:
        time.sleep(1)
        count += 1
        if timeout and count > timeout:
            raise LockException.TimeoutError(f)
        locked = trylock_file(f, reentrant)
    return locked


def trylock_file(f, reentrant=False):
    """Try to lock a file (used in lock_file).

    :param f: name of lock
    :type f: os.path
    :param reentrant: True if this process may have locked this file before,
        defaults to False
    :type reentrant: bool, optional
    :return: True if the file is reached, False otherwise
    :rtype: bool
    """
    lockfile_name = get_lockfile_name(f)
    if not os.path.exists(lockfile_name):
        with open(lockfile_name, 'w') as fh:
            fh.write("{}".format(os.getpid()))
        log.manager.debug("Lock {}".format(lockfile_name))
        return True
    else:
        try:
            pid = get_lock_owner(f)
            if pid == os.getpid() and reentrant:
                log.manager.debug("Lock {}".format(lockfile_name))
                return True
        except ValueError as e:
            pass  # return False

        return False


def is_locked(f):
    """Is the given file locked somewhere else ?

    :param f: the file to test
    :type f: str
    :return: a boolean indicating wether the lock is hold or not.
    :rtype: bool
    """
    lf_name = get_lockfile_name(f)
    return os.path.isfile(os.path.abspath(lf_name))


def get_lock_owner(f):
    """The lock file will contain the process ID owning the lock. This function
    returns it.

    :param f: the original file to mutex
    :type f: str
    :return: the process ID
    :rtype: int
    """
    lf_name = get_lockfile_name(f)
    with open(lf_name, 'r') as fh:
        return int(fh.read().strip())


def program_timeout(sig, frame):
    print("luuu")
    assert(sig == signal.SIGALRM)
    raise CommonException.TimeoutError("Timeout reached")


def start_autokill(timeout=None):
    if isinstance(timeout, int):
        log.manager.print_item(
            "Setting timeout to {} second(s)".format(timeout))
        signal.signal(signal.SIGALRM, program_timeout)

        signal.alarm(timeout)
