import yaml
from os import path
import os
import pcvsrt
import glob
import shutil
import jsonschema
import json
from pcvsrt.utils import logs, files

ROOTPATH = path.abspath(path.join(path.dirname(__file__)))

CONFIG_STORAGES = {
    'global': ROOTPATH + "/share/saves/",
    'user': os.environ['HOME'] + "/.pcvsrt/saves/",
    'local': os.getcwd() + "/.pcvsrt/saves/"
}

CONFIG_BLOCKS = ['compiler', 'runtime', 'machine', 'criterion', 'group']

CONFIG_EXISTING = {}

def scope_order():
    return ['local', 'user', 'global']

def init():
    # this first loop defines configuration order
    for block in CONFIG_BLOCKS:
        CONFIG_EXISTING[block] = {}
        priority_paths = scope_order()
        priority_paths.reverse()
        for token in priority_paths:  # reverse order (overriding)
            CONFIG_EXISTING[block][token] = []
            for config_file in glob.glob(os.path.join(CONFIG_STORAGES[token], block, "*.yml")):
                CONFIG_EXISTING[block][token].append((os.path.basename(config_file)[:-4], config_file))

def list_blocks(kind, scope=None):
    assert (kind in CONFIG_BLOCKS)
    assert (scope in CONFIG_STORAGES.keys() or scope is None)
    if scope is None:
        return CONFIG_EXISTING[kind]
    else:
        return CONFIG_EXISTING[kind][scope]


def check_valid_kind(s):
    if s not in CONFIG_BLOCKS:
        logs.err("Invalid KIND '{}'".format(s),
                 "See --help for more information",
                 abort=1)


def check_valid_scope(s):
    if s not in CONFIG_STORAGES.keys() and s is not None:
        logs.err("Invalid SCOPE '{}'".format(s),
                 "See --help for more information",
                 abort=1)


def check_existing_name(kind, name, scope):
    assert (kind in CONFIG_BLOCKS)
    path = None
    scopes = scope_order() if scope is None else [scope]

    for sc in scopes:
        for pair in CONFIG_EXISTING[kind][sc]:
            if name == pair[0]:
                path = pair[1]
                return (sc, path)
    return (None, None)


def check_path(kind, name, scope):
    return os.path.isfile(compute_path(kind, name, scope))


def compute_path(kind, name, scope):
    assert (scope is not None)
    return os.path.join(CONFIG_STORAGES[scope], kind, name + ".yml")


class ConfigurationScheme:
    _scheme_prefix = os.path.join(ROOTPATH, "share/schemes")

    def __init__(self, kind):
        pass

    def validate(self, conf):
        assert (isinstance(conf, ConfigurationBlock))
        if conf._kind != "compiler":
            logs.warn("VALIDATION: TODO: Scheme for KIND '{}'".format(conf._kind))
            return

        with open(os.path.join(self._scheme_prefix, conf._kind + "-scheme.json"), 'r') as f:
            schema = json.load(f)
            jsonschema.validate(instance=conf._details, schema=schema)


class ConfigurationBlock:
    _template_path = os.path.join(ROOTPATH, "share/templates")
    def __init__(self, kind, name, scope=None):
        check_valid_kind(kind)
        check_valid_scope(scope)
        self._kind = kind
        self._name = name
        self._details = {}
        self._scope, self._file = check_existing_name(kind, name, scope)

    def is_found(self):
        return self._file is not None

    @property
    def scope(self):
        return self._scope

    def fill(self, raw):
        assert (isinstance(raw, dict))
        
        self._details = raw
        self.check()

    def dump(self):
        self.load_from_disk()
        return self._details

    def check(self):
        val = ConfigurationScheme(self._kind)
        val.validate(self)

    def load_from_disk(self):
        
        if self._file is None or not os.path.isfile(self._file):
            logs.err("Invalid name {} for KIND '{}'".format(self._name, self._kind), abort=1)

        logs.info("load {} from '{} ({})'".format(self._name, self._kind, self._scope))
        with open(self._file) as f:
            self._details = yaml.safe_load(f)
            self.check()

    def load_template(self):
        fp = os.path.join(self._template_path, self._kind + "-format.yml") 
        with open(fp, "r") as f:
            self.fill(yaml.load(f, Loader=yaml.FullLoader))
            
    def flush_to_disk(self):
        assert (self._file is not None)
        logs.info("flush {} from '{} ({})'".format(self._name, self._kind, self._scope))

        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.mkdir(prefix_file)
            
        with open(self._file, 'w') as f:
            val = ConfigurationScheme(self._kind)
            val.validate(self)
            yaml.safe_dump(self._details, f)

    def clone(self, clone, scope):
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (self._file is None)

        scope = 'local' if scope is None else scope
        if self._scope is None:  # default creation scope level !
            self._scope = scope
        
        self._file = compute_path(self._kind, self._name, self._scope)
        logs.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))
        
        logs.info("remove {} from '{} ({})'".format(self._name, self._kind, self._scope))
        os.remove(self._file)
        
    def display(self):
        logs.print_header("Configuration display")
        logs.print_section("Scope: {}".format(self._scope.capitalize()))
        logs.print_section("Path: {}".format(self._file))
        if self._details:
            logs.print_section("Details:")
            for k, v in self._details.items():
                logs.print_item("{}: {}".format(k, v))

    def open_editor(self, e=None):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))
        
        files.open_in_editor(self._file, e)
        self.load_from_disk()
        self.check()
