import yaml
import os
import glob
from os import path
from pcvsrt import logs, files, config, globals


def extract_profile_from_token(s, single="right"):
    array = s.split(".")
    if len(array) > 2:
        logs.err("Invalid token", abort=1)
    elif len(array) == 2:
        return (array[0], array[1])
    elif len(array) == 1:
        if single == "left":
            return (s, None)
        else:
            return (None, s)
    else:
        logs.nreach()


PROFILE_STORAGES = dict()
PROFILE_EXISTING = dict()

def init():
    global PROFILE_EXISTING, PROFILE_STORAGES
    PROFILE_STORAGES = { k: os.path.join(v, "saves/profile") for k, v in globals.STORAGES.items()}
    PROFILE_EXISTING = {}
    # this first loop defines configuration order
    priority_paths = globals.storage_order()
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
    scopes = globals.storage_order() if scope is None else [scope]
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
        check_valid_scope(scope)
        self._name = name
        self._scope = scope
        self._details = {}
        tmp, self._file = check_existing_name(name, scope)
        if self._scope is None:
            self._scope = 'local' if tmp is None else tmp 

    def fill(self, raw):
        assert (isinstance(raw, dict))
        check = [val for val in config.CONFIG_BLOCKS if val in raw.keys()]
        if len(check) != len(config.CONFIG_BLOCKS):
            logs.err("All {} configuration blocks are required to build a valid profile!".format(len(config.CONFIG_BLOCKS)), abort=1)

        # fill is called either from 'build' (dict of configurationBlock)
        # of from 'clone' (dict of raw file inputs)
        for k, v in raw.items():
            if isinstance(v, config.ConfigurationBlock):
                self._details[k] = v.dump()
            else:
                self._details[k] = v


    def dump(self):
        self.load_from_disk()
        return self._details

    def is_found(self):
        return self._file is not None

    @property
    def scope(self):
        return self._scope

    @property
    def full_name(self):
        return ".".join([self._scope, self._name])

    def load_from_disk(self):
        if self._file is None or not os.path.isfile(self._file):
            logs.err("Invalid profile name {}".format(self._name), abort=1)

        logs.info("load {} ({})".format(self._name, self._scope))
        with open(self._file) as f:
            self._details = yaml.safe_load(f)

    def load_template(self):
        logs.nimpl()

    def flush_to_disk(self):
        self._file = compute_path(self._name, self._scope)
        assert (not check_path(self._name, self._scope))
        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details, f)

    def clone(self, clone, scope):
        scope = 'local' if scope is None else scope
        if self._scope is None:  # default creation scope level !
            self._scope = scope
        
        self._file = compute_path(self._name, self._scope)
        logs.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        logs.info("delete {}".format(self._file))
        os.remove(self._file)
        pass

    def display(self):
        logs.print_header("Profile View")
        logs.print_section("Scope: {}".format(self._scope.capitalize()))
        logs.print_section("Profile details:")
        if self._details:
            logs.print_section("Details:")
            for k, v in self._details.items():
                logs.print_item("{}: {}".format(k, v))
    
    def open_editor(self, e=None):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))
        
        files.open_in_editor(self._file, e)
        self.load_from_disk()
