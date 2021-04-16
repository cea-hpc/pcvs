import base64
import glob
import os
import tempfile

import click
import jsonschema
import yaml
from addict import Dict

from pcvs import PATH_INSTDIR
from pcvs.helpers import log, system, utils
from pcvs.helpers.exceptions import ConfigException, ValidationException

CONFIG_BLOCKS = ['compiler', 'runtime', 'machine', 'criterion', 'group']
CONFIG_EXISTING = dict()


def init() -> None:
    """init() module function, called when PCVS starts to load 
    any existing configuration files
    """
    global CONFIG_BLOCKS, CONFIG_EXISTING
    CONFIG_EXISTING = {}

    # this first loop defines configuration order
    for block in CONFIG_BLOCKS:
        CONFIG_EXISTING[block] = {}
        priority_paths = utils.storage_order()
        priority_paths.reverse()
        for token in priority_paths:  # reverse order (overriding)
            CONFIG_EXISTING[block][token] = []
            for config_file in glob.glob(os.path.join(utils.STORAGES[token],
                                                      block,
                                                      "*.yml")):
                CONFIG_EXISTING[block][token].append(
                    (os.path.basename(config_file)[:-4], config_file))


def list_blocks(kind, scope=None):
    """Getter to access the list of config names, filtered by kind & scope"""
    assert (kind in CONFIG_BLOCKS)
    assert (scope in utils.STORAGES.keys() or scope is None)
    if scope is None:
        return CONFIG_EXISTING[kind]
    else:
        return CONFIG_EXISTING[kind][scope]


def check_valid_kind(s):
    """Check if the kind given as parameter is a valid one.
        :raises:
            ConfigException.BadTokenError: the kind is not defined or not valid
    """
    if s is None:
        raise ConfigException.BadTokenError("no 'kind' specified")

    if s not in CONFIG_BLOCKS:
        raise ConfigException.BadTokenError("invalid 'kind'")

class ConfigurationBlock:
    """Basic block holding a configuration node.
        This is the object managing basic blocks from user perspective. This is
        not related to MetaConfig() managing PCVS configuration itself (even if
        some are included to it)
    """

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
        """From the stored kind, scope, name, attempt to detect configuration
        block on the file system (i.e. detected during module init())
        """
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
        self._file = os.path.join(
            utils.STORAGES[self._scope], self._kind, self._name + ".yml")
        self._exists = False

    def is_found(self):
        """Is the current config block present on fs ?"""
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
        """convert the configuration Block to a regulard dict.
        This function first load the last version, to ensure being in sync.
        """
        self.load_from_disk()
        return Dict(self._details).to_dict()

    def check(self, fail=True):
        """validate a single configuration block.
            :raises:
                ValidationException.FormatError: config is not valid
        """
        system.ValidationScheme(self._kind).validate(self._details)

    def load_from_disk(self):
        """load the configuration file to populate the current object"""
        if not self._exists:
            raise ConfigException.BadTokenError(
                "{} not defined as '{}' kind".format(self._name, self._kind))

        self.retrieve_file()

        if not os.path.isfile(self._file):
            raise ConfigException.NotFoundError()

        with open(self._file) as f:
            self._details = Dict(yaml.safe_load(f))

    def load_template(self):
        """load from the specific template, to create a new config block"""
        self._exists = True
        self._file = os.path.join(
            PATH_INSTDIR,
            'templates/{}-format.yml'.format(self._kind))
        with open(self._file, 'r') as fh:
            self.fill(yaml.safe_load(fh))

    def flush_to_disk(self):
        """write the configuration block to disk"""
        self.check()
        self.retrieve_file()

        # just in case the block subprefix does not exist yet
        if not self._exists:
            prefix_file = os.path.dirname(self._file)
            if not os.path.isdir(prefix_file):
                os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details.to_dict(), f)

    def clone(self, clone):
        """copy the current object to create an identical one.
            Mainly used to mirror two objects from different scopes
        """
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (not self.is_found())
        assert(clone.is_found())

        self.retrieve_file()
        assert(not os.path.isfile(self._file))

        log.manager.info("Compute target prefix: {}".format(self._file))
        self._details = clone._details

    def delete(self):
        """delete a configuration block from disk"""
        assert (self.is_found())
        assert (os.path.isfile(self._file))

        log.manager.info("remove {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        os.remove(self._file)

    def display(self):
        """Configuration block pretty printer"""
        log.manager.print_header("Configuration display")
        log.manager.print_section("Scope: {}".format(self._scope.capitalize()))
        log.manager.print_section("Path: {}".format(self._file))
        log.manager.print_section("Details:")
        for k, v in self._details.items():
            log.manager.print_item("{}: {}".format(k, v))

    def edit(self, e=None):
        """Open the current block for edition"""
        assert (self._file is not None)

        if not os.path.exists(self._file):
            return
        
        with open(self._file, 'r') as fh:
            stream = fh.read()

        edited_stream = click.edit(stream, editor=e, extension=".yml", require_save=True)
        if edited_stream is not None:
            edited_yaml = Dict(yaml.safe_load(edited_stream))
            system.ValidationScheme(self._kind).validate(edited_yaml)

            self.fill(edited_yaml)
            self.flush_to_disk()

    def edit_plugin(self, e=None):
        if self._kind != "runtime":
            return

        if not os.path.exists(self._file):
            return
        
        stream_yaml = dict()
        with open(self._file, 'r') as fh:
            stream_yaml = yaml.safe_load(fh)
        
        if 'plugin' in stream_yaml.keys():
            plugin_code = base64.b64decode(stream_yaml['plugin']).decode('ascii')
        else:
            plugin_code = """import math
def check_valid_combination(dict_of_combinations=dict()):
    # this dict maps keys (it name) with values (it value)
    # returns True if the combination should be used
    return True"""

        edited_code = click.edit(plugin_code, editor=e, extension=".py", require_save=True)
        if edited_code is not None:
            stream_yaml['plugin'] = base64.b64encode(edited_code.encode('ascii'))
            with open(self._file, 'w') as fh:
                yaml.safe_dump(stream_yaml, fh)
        

