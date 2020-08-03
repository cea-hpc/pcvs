import os
from os import path


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


def set_exec_path(path):
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
        logs.err("Invalid SCOPE '{}'".format(s),
                 "Allowed values are: None, local, user & global",
                 "See --help for more information",
                 abort=1)

LINELENGTH = 93
ROOTPATH = path.abspath(path.join(path.dirname(__file__)))
STORAGES = {
    'global': ROOTPATH,
    'user': os.path.join(os.environ['HOME'], ".pcvsrt"),
    'local': os.path.join(os.getcwd(), '.pcvsrt')
}
