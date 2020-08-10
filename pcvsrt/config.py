import glob
import json
import os

import jsonschema
import yaml
import pkg_resources

from pcvsrt import files, logs
from pcvsrt import globals as pvGlobals

CONFIG_STORAGES = dict()
CONFIG_BLOCKS = list()
CONFIG_EXISTING = dict()


def extract_config_from_token(s, pair="right", single="right"):
    array = s.split(".")
    if len(array) > 3:
        logs.err("Invalid token", abort=1)
    elif len(array) == 3:
        return (array[0], array[1], array[2])
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
        logs.nreach()
    return (None, None, None)  # pragma: no cover


def init():
    global CONFIG_STORAGES, CONFIG_BLOCKS, CONFIG_EXISTING
    CONFIG_STORAGES = {k: os.path.join(v, "saves")
                       for k, v in pvGlobals.STORAGES.items()}
    CONFIG_BLOCKS = {'compiler', 'runtime', 'machine', 'criterion', 'group'}
    CONFIG_EXISTING = {}

    # this first loop defines configuration order
    for block in CONFIG_BLOCKS:
        CONFIG_EXISTING[block] = {}
        priority_paths = pvGlobals.storage_order()
        priority_paths.reverse()
        for token in priority_paths:  # reverse order (overriding)
            CONFIG_EXISTING[block][token] = []
            for config_file in glob.glob(os.path.join(CONFIG_STORAGES[token],
                                                      block,
                                                      "*.yml")):
                CONFIG_EXISTING[block][token].append(
                    (os.path.basename(config_file)[:-4], config_file))


def list_blocks(kind, scope=None):
    assert (kind in CONFIG_BLOCKS)
    assert (scope in CONFIG_STORAGES.keys() or scope is None)
    if scope is None:
        return CONFIG_EXISTING[kind]
    else:
        return CONFIG_EXISTING[kind][scope]


def check_valid_kind(s):
    if s is None:
        logs.err("You must specify a 'kind' when referring to a conf. block",
                 "Allowed values: {}".format(", ".join(CONFIG_BLOCKS)),
                 "See --help for more information",
                 abort=1)

    if s not in CONFIG_BLOCKS:
        logs.err("Invalid KIND '{}'".format(s),
                 "Allowed values: {}".format(", ".join(CONFIG_BLOCKS)),
                 "See --help for more information",
                 abort=1)


def check_existing_name(kind, name, scope):
    assert (kind in CONFIG_BLOCKS)
    path = None
    scopes = pvGlobals.storage_order() if scope is None else [scope]

    for sc in scopes:
        for pair in CONFIG_EXISTING[kind][sc]:
            if name == pair[0]:
                path = pair[1]
                return (sc, path)
    return (None, None)


def compute_path(kind, name, scope):
    assert (scope is not None)
    return os.path.join(CONFIG_STORAGES[scope], kind, name + ".yml")


class ConfigurationScheme:

    def __init__(self, kind):
        pass

    def validate(self, conf):

        assert (isinstance(conf, ConfigurationBlock))
        stream = pkg_resources.resource_string(
            __name__,
            'schemes/{}-scheme.json'.format(conf._kind)),
        
        logs.warn("VAL. Scheme for KIND '{}'".format(conf._kind))
        return
        schema = json.load(stream)
        jsonschema.validate(instance=conf._details, schema=schema)


class ConfigurationBlock:
    _template_path = os.path.join(pvGlobals.ROOTPATH, "share/templates")

    def __init__(self, kind, name, scope=None):
        check_valid_kind(kind)
        pvGlobals.check_valid_scope(scope)
        self._kind = kind
        self._name = name
        self._details = {}
        self._scope = scope
        tmp, self._file = check_existing_name(kind, name, scope)
        if self._scope is None:
            self._scope = 'local' if tmp is None else tmp

    def is_found(self):
        return self._file is not None

    @property
    def full_name(self):
        return ".".join([self._scope, self._kind, self._name])

    @property
    def scope(self):
        return self._scope

    @property
    def short_name(self):
        return self._name

    def fill(self, raw):
        assert (isinstance(raw, dict))
        self._details = raw

    def dump(self):
        self.load_from_disk()
        return self._details

    def check(self):
        val = ConfigurationScheme(self._kind)
        val.validate(self)

    def load_from_disk(self):

        if self._file is None or not os.path.isfile(self._file):
            logs.err("Invalid name {} for KIND '{}'".format(
                self._name, self._kind), abort=1)

        logs.info("load {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        with open(self._file) as f:
            self._details = yaml.safe_load(f)
            self.check()

    def load_template(self):
        stream = pkg_resources.resource_string(__name__, 'templates/{}-format.yml'.format(self._kind))
        self.fill(yaml.load(stream, Loader=yaml.FullLoader))

    def flush_to_disk(self):
        self._file = compute_path(self._kind, self._name, self._scope)

        logs.info("flush {} from '{} ({})'".format(
            self._name, self._kind, self._scope))

        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            val = ConfigurationScheme(self._kind)
            val.validate(self)

            yaml.safe_dump(self._details, f)

    def clone(self, clone):
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (self._file is None)

        self._file = compute_path(self._kind, self._name, self._scope)
        logs.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))

        logs.info("remove {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        os.remove(self._file)

    def display(self):
        logs.print_header("Configuration display")
        logs.print_section("Scope: {}".format(self._scope.capitalize()))
        logs.print_section("Path: {}".format(self._file))
        logs.print_section("Details:")
        for k, v in self._details.items():
           logs.print_item("{}: {}".format(k, v))

    def open_editor(self, e=None):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))
        files.open_in_editor(self._file, e)
        self.load_from_disk()
        self.check()
