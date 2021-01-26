import os
import shutil
import subprocess
from contextlib import contextmanager

import jsonschema
import getpass
import socket
import yaml
import pygit2

from pcvs import BACKUP_NAMEDIR, ROOTPATH
from pcvs.helpers import log, system

####################################
##    STORAGE SCOPE MANAGEMENT    ##
####################################
STORAGES = {
    'global': ROOTPATH,
    'user': os.path.join(os.environ['HOME'], BACKUP_NAMEDIR),
    'local': os.path.join(os.getcwd(), BACKUP_NAMEDIR)
}


def storage_order():
    return ['local', 'user', 'global']


def check_valid_scope(s):
    if s not in storage_order() and s is not None:
        log.err("Invalid SCOPE '{}'".format(s),
                "Allowed values are: None, local, user & global",
                "See --help for more information",
                abort=1)

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
        log.nreach()
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
    found = __determine_local_prefix(path, BACKUP_NAMEDIR)

    # if local is the same as user path, discard
    if found in STORAGES.values():
        found = os.path.join(path, BACKUP_NAMEDIR)
    STORAGES['local'] = found

####################################
####     PATH MANIPULATION      ####
####################################

def create_or_clean_path(prefix, is_dir=True):
    if is_dir:
        if os.path.isdir(prefix):   
            shutil.rmtree(prefix)
        os.mkdir(prefix)
    else:
        if os.path.isfile(prefix):
            os.remove(prefix)

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
####  EDITOR OPENING MANAGMENT  ####
####################################

def assert_editor_valid(override=None):
    editor = "Undefined"
    try:
        if override is None:
            editor = os.environ['EDITOR']
        else:
            editor = override
        if shutil.which(editor, mode=os.X_OK) is None:
            raise Exception
    except:
        log.err("'{}' is not a valid program.".format(editor),
                "Please use --editor or set $EDITOR appropriately")

    return editor

def open_in_editor(*paths, e=None):
    editor = assert_editor_valid(e)
    if shutil.which(editor) is None:
        log.err("'{}' is not a valid editor.".format(editor),
                "Please see the '-e' option!")
    cmd = [
        editor
    ] + list(filter(None, paths))
    log.info("cmd: {}".format(" ".join(cmd)))
    subprocess.check_call(cmd)

####################################
####           MISC.            ####
####################################

def generate_local_variables(label, subprefix):
    base_srcdir = system.get('validation').dirs[label]
    cur_srcdir = os.path.join(base_srcdir, subprefix)
    base_buildir = os.path.join(system.get('validation').output, "test_suite", label)
    cur_buildir = os.path.join(base_buildir, subprefix)
    return base_srcdir, cur_srcdir, base_buildir, cur_buildir

def check_valid_program(p,  succ=log.print_item, fail=log.err):
    if not p:
        return
    try:
        filepath = shutil.which(p)
        res = os.access(filepath, mode=os.X_OK)
    except TypeError:  #which() can return None
        res = False

    if res is True and succ is not None:
        succ("'{}' found at '{}'".format(os.path.basename(p), filepath))

    if res is False and fail is not None:
        fail("{} not found or not a executable".format(p))

    return res



####################################
####   YAML VALIDATION OBJECT   ####
####################################
class ValidationScheme:
    def __init__(self, name):
        self._prefix = name

        with open(os.path.join(
                            ROOTPATH,
                            'schemes/{}-scheme.yml'.format(name)
                        ), 'r') as fh:
            self._scheme = yaml.load(fh, Loader=yaml.FullLoader)

    def validate(self, content, fail_on_error=True, filepath=None):
        try:
            if filepath is None:
                filepath = "'data stream'"
            
            jsonschema.validate(instance=content, schema=self._scheme)
        except jsonschema.exceptions.ValidationError as e:
            if fail_on_error:
                log.err("Wrong format: {} ('{}'):".format(
                                filepath,
                                self._prefix),
                        "{}".format(e.message))
            else:
                raise e
        except Exception as e:
            log.err(
                "Something wrong happen validating {}".format(self._prefix),
                '{}'.format(e)
            )


def request_git_attr(k):
    git_conf = pygit2.Config.get_global_config()
    if k in git_conf:
        return git_conf[k]
    return None

def generate_data_hash(data):
    return str(pygit2.hash(data))

def get_current_username():
    u = request_git_attr('user.name')
    if u is None:
        return getpass.getuser()
    else:
        return u


def get_current_usermail():
    m = request_git_attr('user.email')
    if m is None:
        return "{}@{}".format(get_current_username(), socket.getfqdn())
    else:
        return m