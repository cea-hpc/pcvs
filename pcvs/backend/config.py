import base64
import glob
import os
import tempfile

import jsonschema
import yaml
from addict import Dict

from pcvs import ROOTPATH
from pcvs.helpers import log, utils, system

CONFIG_STORAGES = dict()
CONFIG_BLOCKS = ['compiler', 'runtime', 'machine', 'criterion', 'group']
CONFIG_EXISTING = dict()


def init():
    global CONFIG_STORAGES, CONFIG_BLOCKS, CONFIG_EXISTING
    CONFIG_STORAGES = {k: os.path.join(v, "saves")
                       for k, v in utils.STORAGES.items()}
    CONFIG_EXISTING = {}

    # this first loop defines configuration order
    for block in CONFIG_BLOCKS:
        CONFIG_EXISTING[block] = {}
        priority_paths = utils.storage_order()
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


class ConfigurationBlock:
    def __init__(self, kind, name, scope=None):
        check_valid_kind(kind)
        utils.check_valid_scope(scope)
        self._kind = kind
        self._name = name
        self._details = {}
        self._scope = scope
        self._file = None
        self._exists = False

        self.retrieve_file()

    def retrieve_file(self):
        assert (self._kind in CONFIG_BLOCKS)
        scopes = utils.storage_order() if self._scope is None else [
            self._scope]

        for sc in scopes:
            for pair in CONFIG_EXISTING[self._kind][sc]:
                if self._name == pair[0]:
                    self._file = pair[1]
                    self._scope = sc
                    self._exists = True
                    return

        # default file position when not found
        if self._scope is None:
            self._scope = 'local'
        self._file = self._files = os.path.join(
            CONFIG_STORAGES[self._scope], self._kind, self._name + ".yml")
        self._exists = False

    def is_found(self):
        return self._exists

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
        self._details = Dict(raw)

    def dump(self):
        self.load_from_disk()
        return Dict(self._details).to_dict()

    def check(self, fail=True):
        system.ValidationScheme(self._kind).validate(self._details, fail)

    def load_from_disk(self):
        if not self._exists:
            log.err("Invalid name {} for KIND '{}'".format(
                self._name, self._kind))

        self.retrieve_file()

        if not os.path.isfile(self._file):
            log.err("Internal error: file {} not found!".format(self._file))

        log.info("load {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        with open(self._file) as f:
            self._details = Dict(yaml.safe_load(f))

    def load_template(self):
        self._exists = True
        self._file = os.path.join(
            ROOTPATH,
            'templates/{}-format.yml'.format(self._kind))
        with open(self._file, 'r') as fh:
            self.fill(yaml.load(fh, Loader=yaml.FullLoader))

    def flush_to_disk(self):
        self.check()
        self.retrieve_file()

        log.info("flush {} from '{} ({})'".format(
            self._name, self._kind, self._scope))

        # just in case the block subprefix does not exist yet
        if not self._exists:
            prefix_file = os.path.dirname(self._file)
            if not os.path.isdir(prefix_file):
                os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details.to_dict(), f)

    def clone(self, clone):
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (not self.is_found())
        assert(clone.is_found())

        self.retrieve_file()
        assert(not os.path.isfile(self._file))

        log.info("Compute target prefix: {}".format(self._file))
        self._details = clone._details

    def delete(self):
        assert (self.is_found())
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

        e = utils.assert_editor_valid(e)

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
                    content = base64.b64decode(
                        stream['plugin']).decode('ascii')
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
            utils.open_in_editor(fname.name,
                                 fplugin.name if fplugin else None,
                                 e=e)
        except Exception:
            log.warn("Issue with opening the conf. block. Stop!")
            return

        # now, dump back temp file to the original saves
        try:
            fname.seek(0)
            self._details = Dict(yaml.load(fname, Loader=yaml.FullLoader))
        except yaml.YAMLError as e:
            log.err("Failure when editing conf. block:", '{}'.format(e))
        except TypeError:
            self._details = dict()

        if fplugin:
            fplugin.seek(0)
            stream_plugin = fplugin.read()
            if len(stream_plugin) > 0:
                self._details['plugin'] = base64.b64encode(
                    stream_plugin.encode('ascii'))

        try:
            self.check(fail=False)
        except jsonschema.exceptions.ValidationError as e:
            with tempfile.NamedTemporaryFile(mode="w+",
                                             suffix=".yml.rej",
                                             prefix=self.full_name,
                                             delete=False) as rej_fh:
                yaml.dump(stream, rej_fh)

                log.err("Invalid format: {}".format(e.message),
                        "Rejected file: {}".format(rej_fh.name),
                        "See 'pcvs check' to validate external resource",
                        "before the importation.")

        # delete temp files (replace by 'with...' ?)
        fname.close()
        if fplugin:
            fplugin.close()

        self.flush_to_disk()
