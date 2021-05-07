import base64
import glob
import os

import click
import jsonschema
import yaml
from addict import Dict

from pcvs import PATH_INSTDIR
from pcvs.backend import config
from pcvs.helpers import git, log, system, utils
from pcvs.helpers.exceptions import ProfileException, ValidationException

PROFILE_EXISTING = dict()

def init():
    global PROFILE_EXISTING
    PROFILE_EXISTING = {}
    # this first loop defines configuration order
    priority_paths = utils.storage_order()
    priority_paths.reverse()
    for token in priority_paths:  # reverse order (overriding)
        PROFILE_EXISTING[token] = []
        for pfile in glob.glob(os.path.join(utils.STORAGES[token], 'profile', "*.yml")):
            PROFILE_EXISTING[token].append(
                (os.path.basename(pfile)[:-4], pfile))


def list_profiles(scope=None):
    assert (scope in utils.STORAGES.keys() or scope is None)
    if scope is None:
        return PROFILE_EXISTING
    else:
        return PROFILE_EXISTING[scope]


class Profile:
    def __init__(self, name, scope=None):
        utils.check_valid_scope(scope)
        self._name = name
        self._scope = scope
        self._details = Dict()
        self._exists = False
        self._file = None

        self._retrieve_file()

    def _retrieve_file(self):
        self._file = None
        if self._scope is None:
            allowed_scopes = utils.storage_order()
        else:
            allowed_scopes = [self._scope]

        for sc in allowed_scopes:
            for pair in PROFILE_EXISTING[sc]:
                if self._name == pair[0]:
                    self._file = pair[1]
                    self._scope = sc
                    self._exists = True
                    return

        if self._scope is None:
            self._scope = 'local'
        self._file = os.path.join(
            utils.STORAGES[self._scope], 'profile', self._name + ".yml")
        self._exists = False

    def get_unique_id(self):
        return git.generate_data_hash(str(self._details))

    def fill(self, raw):
        # some checks
        assert (isinstance(raw, dict))
        
        # fill is called either from 'build' (dict of configurationBlock)
        # of from 'clone' (dict of raw file inputs)
        for k, v in raw.items():
            if isinstance(v, config.ConfigurationBlock):
                self._details[k] = Dict(v.dump())
            else:
                self._details[k] = v

    def dump(self):
        self.load_from_disk()
        return Dict(self._details).to_dict()

    def is_found(self):
        return self._exists

    @property
    def scope(self):
        return self._scope

    @property
    def full_name(self):
        return ".".join([self._scope, self._name])

    def load_from_disk(self):
        if not self._exists:
            raise ProfileException.NotFoundError(self._name)
        self._retrieve_file()

        if not os.path.isfile(self._file):
            raise ProfileException.NotFoundError(self._file)

        log.manager.info("load {} ({})".format(self._name, self._scope))
        with open(self._file) as f:
            self._details = Dict(yaml.safe_load(f))

    def load_template(self):
        self._exists = True
        self._file = None
        for kind in config.CONFIG_BLOCKS:
            filepath = os.path.join(PATH_INSTDIR, "templates", "{}-format.yml".format(kind))
            with open(filepath, "r") as fh:
                self.fill({kind: yaml.safe_load(fh)})

    def check(self, fail=True):
        for kind in config.CONFIG_BLOCKS:
            if kind not in self._details:
                raise ValidationException.FormatError(
                    "Missing '{}' in profile".format(kind))
            system.ValidationScheme(kind).validate(self._details[kind])

    def flush_to_disk(self):
        self._retrieve_file()
        self.check()

        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details.to_dict(), f)

    def clone(self, clone):
        self._retrieve_file()
        log.manager.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        log.manager.info("delete {}".format(self._file))
        os.remove(self._file)
        pass

    def display(self):
        log.manager.print_header("Profile View")
        log.manager.print_section("Scope: {}".format(self._scope.capitalize()))
        log.manager.print_section("Profile details:")
        if self._details:
            log.manager.print_section("Details:")
            for k, v in self._details.items():
                log.manager.print_item("{}: {}".format(k, v))

    def edit(self, e=None):
        assert (self._file is not None)

        if not os.path.exists(self._file):
            return
        
        with open(self._file, 'r') as fh:
            stream = fh.read()

        edited_stream = click.edit(stream, editor=e, extension=".yml", require_save=True)
        if edited_stream is not None:
            edited_yaml = Dict(yaml.safe_load(edited_stream))
            self.fill(edited_yaml)
            self.check()
            self.flush_to_disk()

    def edit_plugin(self, e=None):
        if not os.path.exists(self._file):
            return
        
        stream_yaml = dict()
        with open(self._file, 'r') as fh:
            stream_yaml = yaml.safe_load(fh)
        
        if 'plugin' in stream_yaml['runtime'].keys():
            plugin_code = base64.b64decode(stream_yaml['runtime']['plugin']).decode('ascii')
        else:
            plugin_code = """import math
def check_valid_combination(dict_of_combinations=dict()):
    # this dict maps keys (it name) with values (it value)
    # returns True if the combination should be used
    return True"""

        edited_code = click.edit(plugin_code, editor=e, extension=".py", require_save=True)
        if edited_code is not None:
            stream_yaml['runtime']['plugin'] = base64.b64encode(edited_code.encode('ascii'))
            with open(self._file, 'w') as fh:
                yaml.safe_dump(stream_yaml, fh)

    def split_into_configs(self, prefix, blocklist, scope=None):
        objs = list()
        if 'all' in blocklist:
            blocklist = config.CONFIG_BLOCKS
        if scope is None:
            scope = self._scope

        for name in blocklist:
            c = config.ConfigurationBlock(name, prefix, scope)
            if c.is_found():
                raise ProfileException.AlreadyExistError(c.full_name)
            else:
                c.fill(self._details[name])
                objs.append(c)
        return objs

    @property
    def compiler(self):
        return self._details['compiler']

    @property
    def runtime(self):
        return self._details['runtime']

    @property
    def criterion(self):
        return self._details['criterion']

    @property
    def group(self):
        return self._details['group']

    @property
    def machine(self):
        return self._details['machine']
