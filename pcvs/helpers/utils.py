import os
import shutil
import fcntl
import time
from contextlib import contextmanager

from pcvs import (NAME_BUILDFILE, NAME_BUILDIR, NAME_SRCDIR, PATH_HOMEDIR,
                  PATH_INSTDIR)
from pcvs.helpers.exceptions import CommonException, RunException, LockException
from pcvs.helpers.system import MetaConfig
from pcvs.helpers import log

####################################
##    STORAGE SCOPE MANAGEMENT    ##
####################################
STORAGES = {
    'global': PATH_INSTDIR,
    'user': PATH_HOMEDIR,
    'local': os.path.join(os.getcwd(), NAME_SRCDIR)
}


def create_home_dir():
    if not os.path.exists(PATH_HOMEDIR):
        os.makedirs(PATH_HOMEDIR)


def storage_order():
    """returns scopes in order of searching

    :return: a list of scopes
    :rtype: list
    """
    return ['local', 'user', 'global']


def check_valid_scope(s):
    """check if argument is a valid scope (local, user, global)

    :param s: scope to check
    :type s: str
    :raises CommonException.BadTokenError: the argument is not a valid scope
    """
    if s not in storage_order() and s is not None:
        raise CommonException.BadTokenError(s)

def extract_infos_from_token(s, pair="right", single="right", maxsplit=3):
    """Extract fields from tokens (a, b, c) from user's string

    Args:
        s (string): the input string
        pair (str, optional): padding side when only 2 tokens found. Defaults to "right".
        single (str, optional): padding side when only 1 token found. Defaults to "right".

    Returns:
        3-string-tuple: mapping (scope, kind, name), any of them may be null
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
    """search for the ``local`` storage in the current (or parent) directory

    :param path: 
    :type path: os.path, str
    :param prefix: 
    :type prefix: os.path, str
    :return: 
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
    """sets the prefix for the ``local`` storage

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
    """creates a path or cleans it if it already exists

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
    """change the working directory

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

####################################
####           MISC.            ####
####################################

def generate_local_variables(label, subprefix):
    """returns directories from PCVS working tree :

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
    base_buildir = os.path.join(MetaConfig.root.validation.output, "test_suite", label)
    cur_buildir = os.path.join(base_buildir, subprefix)        

    return base_srcdir, cur_srcdir, base_buildir, cur_buildir

def check_valid_program(p, succ=None, fail=None, raise_if_fail=True):
    """checks if p is a valid program, using the ``which`` function

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
    except TypeError:  #which() can return None
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
        """find the build directory from the ``path`` prefix

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

def unlock_file(f):
    """Remove lock from a directory

    :param f: file locking the directory
    :type f: os.path
    """
    if os.path.exists(f) and os.path.isfile(f):
        with open(f, "w+") as fh:
            os.remove(f)
            log.manager.debug("Unlock {}".format(f))


def lock_file(f, reentrant=False, timeout=None):
    """try to lock a directory

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
    """try to lock a file (used in lock_file)

    :param f: name of lock
    :type f: os.path
    :param reentrant: True if this process may have locked this file before,
        defaults to False
    :type reentrant: bool, optional
    :return: True if the file is reached, False otherwise
    :rtype: bool
    """
    if not os.path.exists(f):
        with open(f, 'w') as fh:
            fh.write("{}".format(os.getpid()))
        log.manager.debug("Lock {}".format(f))
        return True
    else:
        with open(f, 'r') as fh:
            pid = int(fh.read().strip())
        
        if pid == os.getpid() and reentrant:
            log.manager.debug("Lock {}".format(f))
            return True
        
        return False