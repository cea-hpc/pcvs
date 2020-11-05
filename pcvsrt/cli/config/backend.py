import base64
import glob
import os
import pprint
import yaml
from addict import Dict
import tempfile

import pcvsrt
from pcvsrt.helpers import io, log, validation
from pcvsrt.helpers.system import sysTable


CONFIG_STORAGES = dict()
CONFIG_BLOCKS = list()
CONFIG_EXISTING = dict()


def extract_config_from_token(s, pair="right", single="right"):
    array = s.split(".")
    if len(array) > 3:
        log.err("Invalid token")
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
        log.nreach()
    return (None, None, None)  # pragma: no cover


def init():
    global CONFIG_STORAGES, CONFIG_BLOCKS, CONFIG_EXISTING
    CONFIG_STORAGES = {k: os.path.join(v, "saves")
                       for k, v in io.STORAGES.items()}
    CONFIG_BLOCKS = {'compiler', 'runtime', 'machine', 'criterion', 'group'}
    CONFIG_EXISTING = {}

    # this first loop defines configuration order
    for block in CONFIG_BLOCKS:
        CONFIG_EXISTING[block] = {}
        priority_paths = io.storage_order()
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
        log.err("You must specify a 'kind' when referring to a conf. block",
                "Allowed values: {}".format(", ".join(CONFIG_BLOCKS)),
                "See --help for more information",
                abort=1)

    if s not in CONFIG_BLOCKS:
        log.err("Invalid KIND '{}'".format(s),
                "Allowed values: {}".format(", ".join(CONFIG_BLOCKS)),
                "See --help for more information",
                abort=1)


def check_existing_name(kind, name, scope):
    assert (kind in CONFIG_BLOCKS)
    path = None
    scopes = io.storage_order() if scope is None else [scope]

    for sc in scopes:
        for pair in CONFIG_EXISTING[kind][sc]:
            if name == pair[0]:
                path = pair[1]
                return (sc, path)
    return (None, None)


def compute_path(kind, name, scope):
    assert (scope is not None)
    return os.path.join(CONFIG_STORAGES[scope], kind, name + ".yml")


class ConfigurationBlock:
    _template_path = os.path.join(io.ROOTPATH, "share/templates")

    def __init__(self, kind, name, scope=None):
        check_valid_kind(kind)
        io.check_valid_scope(scope)
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
        self._details = raw if raw else dict()

    def dump(self):
        self.load_from_disk()
        return Dict(self._details).to_dict()

    def check(self, fail=True):
        validation.ValidationScheme(self._kind).validate(self._details, fail)

    def load_from_disk(self):

        if self._file is None or not os.path.isfile(self._file):
            log.err("Invalid name {} for KIND '{}'".format(
                self._name, self._kind))

        log.info("load {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        with open(self._file) as f:
            self._details = yaml.safe_load(f)

    def load_template(self):
        with open(os.path.join(
                    pcvsrt.ROOTPATH,
                    'templates/{}-format.yml'.format(self._kind)), 'r') as fh:
            self.fill(yaml.load(fh, Loader=yaml.FullLoader))

    def flush_to_disk(self):
        self._file = compute_path(self._kind, self._name, self._scope)
        
        self.check()
        
        log.info("flush {} from '{} ({})'".format(
            self._name, self._kind, self._scope))

        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)

        
        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details, f)

    def clone(self, clone):
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (self._file is None)

        self._file = compute_path(self._kind, self._name, self._scope)
        log.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        assert (self._file is not None)
        assert (os.path.isfile(self._file))

        log.info("remove {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        os.remove(self._file)

    def display(self):
        log.print_header("Configuration display")
        log.print_section("Scope: {}".format(self._scope.capitalize()))
        log.print_section("Path: {}".format(self._file))
        log.print_section("Details:")
        for k, v in self._details.items():
            log.print_item("{}: {}".format(k, v))

    def open_editor(self, e=None):
        assert (self._file is not None)
        
        if not os.path.exists(self._file):
            return

        e = io.assert_editor_valid(e)
        
        fname = tempfile.NamedTemporaryFile(
                mode='w+',
                prefix="{}-".format(self.full_name),
                suffix=".yml")
        fplugin = None
        if self._kind == 'runtime':
            fplugin = tempfile.NamedTemporaryFile(
                mode='w+',
                prefix="{}-".format(self.full_name),
                suffix=".py")
        with open(self._file, 'r') as f:
            stream = yaml.load(f, Loader=yaml.FullLoader)
            if stream:
                yaml.dump(stream, fname)

            if fplugin:
                if stream and 'plugin' in stream:
                    content = base64.b64decode(stream['plugin']).decode('ascii')
                else:
                    content = """import math

def check_valid_combination(dict_of_combinations=dict()):
    # this dict maps keys (it name) with values (it value)
    # returns True if the combination should be used
    return True
"""
                fplugin.write(content)
                fplugin.flush()
        try:
            io.open_in_editor(fname.name,
                              fplugin.name if fplugin else None,
                              e=e)
        except:
            log.warn("Issue with opening the conf. block. Stop!")
            return
       
        #now, dump back temp file to the original saves
        try:
            fname.seek(0)
            self._details = dict(yaml.load(fname, Loader=yaml.FullLoader))
        except yaml.YAMLError as e:
            log.err("Failure when editing conf. block:", '{}'.format(e))
        except TypeError:
            self._details = dict()

        if fplugin:
            fplugin.seek(0)
            stream_plugin = fplugin.read()
            if len(stream_plugin) > 0:
                self._details['plugin'] = base64.b64encode(stream_plugin.encode('ascii'))

        # delete temp files (replace by 'with...' ?)
        fname.close()
        if fplugin:
            fplugin.close()
        
        self.flush_to_disk()
