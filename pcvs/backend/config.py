import base64
import glob
import os

import click
from ruamel.yaml import YAML

from pcvs import PATH_INSTDIR
from pcvs.helpers import log, system, utils
from pcvs.helpers.exceptions import ConfigException
from pcvs.helpers.system import MetaDict

CONFIG_BLOCKS = ['compiler', 'runtime', 'machine', 'criterion', 'group']
CONFIG_EXISTING = dict()


def init() -> None:
    """Load configuration tree available on disk.

    This function is called when PCVS starts to load 3-scope configuration
    trees.
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
    """Get available configuration blocks, as present on disk.

    :param kind: configBlock kind (see ``CONFIG_BLOCKS`` for possible values)
    :type kind: str, one of ``CONFIG_BLOCKS`` values
    :param scope: where the configblocks is located, defaults to None
    :type scope: 'user', 'global' or 'local', optional
    :return: list blocks with specified kind, restricted by scope (if any)
    :rtype: dict of config blocks
    """
    assert (kind in CONFIG_BLOCKS)
    assert (scope in utils.STORAGES.keys() or scope is None)
    if scope is None:
        return CONFIG_EXISTING[kind]
    else:
        return CONFIG_EXISTING[kind][scope]


def list_templates():
    """List available templates to be used for boostraping config. blocks.

    :return: a list of valid templates.
    :rtype: list"""
    array = list()
    for f in os.listdir(os.path.join(PATH_INSTDIR, "templates/config")):
        array.append(os.path.splitext(f)[0])

    return array


def check_valid_kind(s):
    """Assert the parameter is a valid kind.

    Kind are defined by ``CONFIG_BLOCKS`` module attribute.

    :param s: the kind to validate
    :type s: str
    :raises BadTokenError: Kind is None
    :raises BadTokenError: Kind is not in allowed values.
    """
    if s is None:
        raise ConfigException.BadTokenError("no 'kind' specified")

    if s not in CONFIG_BLOCKS:
        raise ConfigException.BadTokenError("invalid 'kind'")


class ConfigurationBlock:
    """Handle the basic configuration block, smallest part of a profile.

        From a user persperctive, a basic block is a dict, gathering in a Python
        object informations relative to the configuration of a single component.
        In PCVS, there is 5 types of components:
            * Compiler-oriented (defining compiler commands)
            * Runtime-oriented (setting runtime & parametrization)
            * Machine-oriented (Defining resources used for execution)
            * Group-oriented (used a templates to globally describe tests)
            * Criterion-oriented (range of parameters used to run a test-suite)

        This class helps to manage any of these config blocks above. The
        distinction between them is carried over by an instance attribute
        ``_kind``.

        .. note::
            This object can easily be confused with :class:`system.Config`.
            While ConfigurationBlocks are from a user perspective,
            system.Config handles the internal configuration tree, on which runs
            rely. Nonetheless, both could be merged into a single representation
            in later versions.

        :param str _kind: which component this object describes
        :param str _name: block name 
        :param dict details: block content
        :param str _scope: block scope, may be None
        :param str _file: absolute path for the block on disk
        :param bool _exists: True if the block exist on disk
    """

    def __init__(self, kind, name, scope=None):
        """Constructer method

        :param kind: which component to initialize this basicblock with
        :type kind: str, one of ``CONFIG_BLOCKS`` values
        :param name: block name
        :type name: str
        :param scope: block scope, defaults to 'local'
        :type scope: str, optional
        """
        check_valid_kind(kind)
        utils.check_valid_scope(scope)
        self._kind = kind
        self._name = name
        self._details = {}
        self._scope = scope
        self._file = None
        self._exists = False

        self.retrieve_file()

    def retrieve_file(self) -> None:
        """Associate the actual filepath to the config block.

        From the stored kind, scope, name, attempt to detect configuration
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
        if not os.path.isfile(self._file):
            self._exists = False

    def is_found(self) -> bool:
        """Check if the current config block is present on fs.

        :return: True if it exists
        :rtype: bool
        """
        return self._exists

    @property
    def full_name(self) -> str:
        """Return complete block label (scope + kind + name)

        :return: the fully-qualified name.
        :rtype: str
        """
        return ".".join([self._scope, self._kind, self._name])

    @property
    def ref_file(self) -> str:
        """Return filepath associated with current config block.

        :return: the filepath, may be None
        :rtype: str
        """
        return self._file

    @property
    def scope(self) -> str:
        """Return block scope.

        :return: the scope, resolved if needed.
        :rtype: str
        """
        return self._scope

    @property
    def short_name(self) -> str:
        """Return the block label only.

        :return: the short name (may conflict with other config block)
        :rtype: str
        """
        return self._name

    def fill(self, raw) -> None:
        """Populate the block content with parameters.

        :param raw: the data to fill.
        :type raw: dict
        """
        self._details = MetaDict(raw)

    def dump(self) -> dict:
        """Convert the configuration Block to a regular dict.

        This function first load the last version, to ensure being in sync.

        :return: a regular dict() representing the config blocK
        :rtype: dict
        """
        self.load_from_disk()
        return MetaDict(self._details).to_dict()

    def check(self) -> None:
        """Validate a single configuration block according to its scheme."""
        system.ValidationScheme(self._kind).validate(
            self._details, filepath=self.full_name)

    def load_from_disk(self) -> None:
        """load the configuration file to populate the current object.

        :raises BadTokenError: the scope/kind/name tuple does not refer to a
            valid file.
        :raises NotFoundError: The target file does not exist
        """

        if not self._exists:
            raise ConfigException.BadTokenError(
                "{} not defined as '{}' kind".format(self._name, self._kind))

        self.retrieve_file()

        if not os.path.isfile(self._file):
            raise ConfigException.NotFoundError()

        with open(self._file) as f:
            self._details = MetaDict(YAML(typ='safe').load(f))

    def load_template(self, name=None) -> None:
        """load from the specific template, to create a new config block"""
        self._exists = True
        if not name:
            name = self._kind + ".default"
        filepath = os.path.join(PATH_INSTDIR,
                                'templates/config/{}.yml'.format(name))

        if not os.path.isfile(filepath):
            raise ConfigException.NotFoundError("{}".format(name))

        with open(filepath, 'r') as fh:
            self.fill(YAML(typ='safe').load(fh))

    def flush_to_disk(self) -> None:
        """write the configuration block to disk"""
        self.check()
        self.retrieve_file()

        # just in case the block subprefix does not exist yet
        if not self._exists:
            prefix_file = os.path.dirname(self._file)
            if not os.path.isdir(prefix_file):
                os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yml = YAML(typ='safe')
            yml.default_flow_style = False
            yml.dump(self._details.to_dict(), f)

        self._exists = True

    def clone(self, clone: 'ConfigurationBlock') -> None:
        """Copy the current object to create an identical one.

        Mainly used to mirror two objects from different scopes.

        :param clone: the object to mirror
        :type clone: :class:`ConfigurationBlock`
        """
        assert (isinstance(clone, ConfigurationBlock))
        assert (clone._kind == self._kind)
        assert (not self.is_found())
        assert(clone.is_found())

        self.retrieve_file()
        assert(not os.path.isfile(self._file))

        log.manager.info("Compute target prefix: {}".format(self._file))
        self._details = clone._details

    def delete(self) -> None:
        """Delete a configuration block from disk"""
        assert (self.is_found())
        assert (os.path.isfile(self._file))

        log.manager.info("remove {} from '{} ({})'".format(
            self._name, self._kind, self._scope))
        os.remove(self._file)

    def display(self) -> None:
        """Configuration block pretty printer"""
        log.manager.print_header("Configuration display")
        log.manager.print_section("Scope: {}".format(self._scope.capitalize()))
        log.manager.print_section("Path: {}".format(self._file))
        log.manager.print_section("Details:")
        for k, v in self._details.items():
            log.manager.print_item("{}: {}".format(k, v))

    def edit(self, e=None) -> None:
        """Open the current block for edition.

        :raises Exception: Something occured on the edited version.
        :param e: the EDITOR to use instead of default.
        :type e: str
        """
        assert (self._file is not None)

        if not os.path.exists(self._file):
            return

        with open(self._file, 'r') as fh:
            stream = fh.read()

        edited_stream = click.edit(
            stream, editor=e, extension=".yml", require_save=True)
        if edited_stream is not None:
            try:
                edited_yaml = MetaDict(YAML(typ='safe').load(edited_stream))
                system.ValidationScheme(self._kind).validate(edited_yaml)
                self.fill(edited_yaml)
                self.flush_to_disk()
            except Exception as e:
                fname = "./rej{}-{}.yml".format(
                    random.randint(0, 1000), self.full_name)
                with open(fname, "w") as fh:
                    fh.write(edited_stream)
                raise e

    def edit_plugin(self, e=None) -> None:
        """Special case to handle 'plugin' key for 'runtime' blocks.

        This allows to edit a de-serialized version of the 'plugin' field. By
        default, data are stored as a base64 string. In order to let user edit
        the code, the string need to be decoded first.

        :param e: the editor to use instead of defaults
        :type e: str
        """
        if self._kind != "runtime":
            return

        if not os.path.exists(self._file):
            return

        stream_yaml = dict()
        with open(self._file, 'r') as fh:
            stream_yaml = YAML(typ='safe').load(fh)

        if 'plugin' in stream_yaml.keys():
            plugin_code = base64.b64decode(
                stream_yaml['plugin']).decode('ascii')
        else:
            plugin_code = """import math
from pcvs.plugins import Plugin

class MyPlugin(Plugin):
    step = Plugin.Step.TEST_EVAL
    def run(self, *args, **kwargs):
    # this dict maps keys (it name) with values (it value)
    # returns True if the combination should be used
    return True
"""

        edited_code = click.edit(
            plugin_code, editor=e, extension=".py", require_save=True)
        if edited_code is not None:
            stream_yaml['plugin'] = base64.b64encode(
                edited_code.encode('ascii'))
            with open(self._file, 'w') as fh:
                YAML(typ='safe').dump(stream_yaml, fh)
