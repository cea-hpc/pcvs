import os
import shutil
import subprocess
from contextlib import contextmanager

import jsonschema
import yaml

from pcvs import NAME_SRCDIR, PATH_HOMEDIR, PATH_INSTDIR
from pcvs.helpers.exceptions import CommonException, RunException
from pcvs.helpers.system import MetaConfig

####################################
##    STORAGE SCOPE MANAGEMENT    ##
####################################
STORAGES = {
    'global': PATH_INSTDIR,
    'user': PATH_HOMEDIR,
    'local': os.path.join(os.getcwd(), NAME_SRCDIR)
}


def storage_order():
    return ['local', 'user', 'global']


def check_valid_scope(s):
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
    assert (os.path.isdir(path))
    found = __determine_local_prefix(path, NAME_SRCDIR)

    # if local is the same as user path, discard
    if found in STORAGES.values():
        found = os.path.join(path, NAME_SRCDIR)
    STORAGES['local'] = found

####################################
####     PATH MANIPULATION      ####
####################################

def create_or_clean_path(prefix):
    if not os.path.exists(prefix):
        return
    if os.path.isdir(prefix):
        shutil.rmtree(prefix)
        os.mkdir(prefix)
    elif os.path.isfile(prefix):
        os.remove(prefix)
    else:
        raise CommonException.IOError(prefix)

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

####################################
####           MISC.            ####
####################################

def generate_local_variables(label, subprefix):
    if label not in MetaConfig.root.validation.dirs:
        raise CommonException.NotFoundError(label)

    base_srcdir = MetaConfig.root.validation.dirs[label]
    cur_srcdir = os.path.join(base_srcdir, subprefix)
    base_buildir = os.path.join(MetaConfig.root.validation.output, "test_suite", label)
    cur_buildir = os.path.join(base_buildir, subprefix)        

    return base_srcdir, cur_srcdir, base_buildir, cur_buildir

def check_valid_program(p, succ=None, fail=None, raise_if_fail=True):
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
