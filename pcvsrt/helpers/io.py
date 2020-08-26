import os
import shutil
import subprocess
from contextlib import contextmanager

from pcvsrt.helpers import log
from pcvsrt.helpers.system import sysTable

ROOTPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGES = {
    'global': ROOTPATH,
    'user': os.path.join(os.environ['HOME'], ".pcvsrt"),
    'local': os.path.join(os.getcwd(), '.pcvsrt')
}


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


def create_or_clean_path(prefix):
    if os.path.isdir(prefix):
        shutil.rmtree(prefix)
    os.mkdir(prefix)


def set_local_path(path):
    assert (os.path.isdir(path))
    found = __determine_local_prefix(path, ".pcvsrt")

    # if local is the same as user path, discard
    if found in STORAGES.values():
        found = os.path.join(path, ".pcvsrt")
    STORAGES['local'] = found


def storage_order():
    return ['local', 'user', 'global']


def check_valid_scope(s):
    if s not in storage_order() and s is not None:
        log.err("Invalid SCOPE '{}'".format(s),
                "Allowed values are: None, local, user & global",
                "See --help for more information",
                abort=1)


def generate_local_variables(label, subprefix):
    base_srcdir = sysTable.rootdirs[label]
    cur_srcdir = os.path.join(base_srcdir, subprefix)
    base_buildir = os.path.join(sysTable.validation.output, "test_suite", label)
    cur_buildir = os.path.join(base_buildir, subprefix)
    return base_srcdir, cur_srcdir, base_buildir, cur_buildir


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
    if shutil.which(editor) is None:
        log.err("'{}' is not a valid editor.".format(editor),
                "Please see the '-e' option!", abort=1)
    subprocess.run([editor, path])


class MetaDict(dict):
    def __init__(self, obj=None):
        if obj is None:
            pass
        elif isinstance(obj, dict):
            for k in obj:
                self.__setitem__(k, obj[k])
        else:
            raise TypeError('expect dict to initialize')

    def __getitem__(self, key):
        if '.' not in key:
            return dict.__getitem__(self, key)

        k, next_k = key.split('.', 1)
        subdict = dict.__getitem__(self, k)
        if not isinstance(subdict, MetaDict):
            raise KeyError("Failed to get {} from {}", next_k, k)
        return subdict[next_k]

    def __setitem__(self, key, value):
        if '.' not in key:
            if isinstance(value, dict) and not isinstance(value, MetaDict):
                print(value)
                value = MetaDict(value)
        dict.__setitem__(self, key, value)

    def __contains__(self, key):
        if '.' not in key:
            return dict.__contains__(self, key)
        k, next_k = key.split('.', 1)
        subdict = dict.__getitem__(self, k)
        if not isinstance(subdict, MetaDict):
            return False
        return next_k in subdict

    def setdefault(self, key, dflt):
        if key not in self:
            self[key] = dflt
        return self[key]

    __setattr__ = __setitem__
    __getattr__ = __getitem__
