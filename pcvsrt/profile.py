import yaml
import os
import glob
from os import path
from pcvsrt.utils import logs, files
from pcvsrt import config


ROOTPATH = path.abspath(path.join(path.dirname(__file__)))

PROFILE_STORAGES = {
    'global': ROOTPATH + "/share/saves/profile",
    'user': os.environ['HOME'] + "/.pcvsrt/saves/profile",
    'local': os.getcwd() + "/.pcvsrt/saves/profile"
}

PROFILE_EXISTING = {}

def scope_order():
    return ['local', 'user', 'global']


def init():
    # this first loop defines configuration order
    priority_paths = scope_order()
    priority_paths.reverse()
    for token in priority_paths:  # reverse order (overriding)
        PROFILE_EXISTING[token] = []
        for pfile in glob.glob(os.path.join(PROFILE_STORAGES[token], "*.yml")):
            PROFILE_EXISTING[token].append((os.path.basename(pfile)[:-4], pfile))


def check_valid_scope(s):
    if s not in PROFILE_STORAGES.keys() and s is not None:
        logs.err("Invalid SCOPE '{}'".format(s),
                 "See --help for more information",
                 abort=1)


def check_existing_name(name, scope):
    path = None
    scopes = scope_order() if scope is None else [scope]
    for sc in scopes:
        for pair in PROFILE_EXISTING[sc]:
            if name == pair[0]:
                path = pair[1]
                return (sc, path)
    return (None, None)


def check_path(name, scope):
    return os.path.isfile(compute_path(name, scope))


def compute_path(name, scope):
    assert (scope is not None)
    return os.path.join(PROFILE_STORAGES[scope], name + ".yml")


def list_profiles(scope=None):
    assert (scope in PROFILE_STORAGES.keys() or scope is None)
    if scope is None:
        return PROFILE_EXISTING
    else:
        return PROFILE_EXISTING[scope]


class Profile:
    def __init__(self, name, scope=None):
        self._name = name
        self._scope = scope
        self._details = {}
        self._scope, self._file = check_existing_name(name, scope)

    def fill(self, raw):
        assert (isinstance(raw, dict))
        self._details = raw

    def dump(self):
        self.load_from_disk()
        return self._details

    def is_found(self):
        return self._file is not None

    @property
    def scope(self):
        return self._scope

    def load_from_disk(self):
        if self._file is None or not os.path.isfile(self._file):
            logs.err("Invalid profile name {}".format(self._name), abort=1)

        logs.info("load {} ({})".format(self._name, self._scope))
        with open(self._file) as f:
            self._details = yaml.safe_load(f)

    def load_template(self):
        logs.nimpl()

    def flush_to_disk(self):
        pass

    def clone(self):
        pass

    def delete(self):
        pass

    def display(self):
        logs.print_header("Profile View")
        logs.print_section("Scope: {}".format(self._scope.capitalize()))
    
    def open_editor(self, e=None):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))
        
        files.open_in_editor(self._file, e)
        self.load_from_disk()
