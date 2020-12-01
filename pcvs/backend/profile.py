import base64
import glob
import os
import tempfile

import jsonschema
import yaml
from addict import Dict

from pcvs import ROOTPATH
from pcvs.backend import config
from pcvs.helpers import log, utils

PROFILE_STORAGES = dict()
PROFILE_EXISTING = dict()


def init():
    global PROFILE_EXISTING, PROFILE_STORAGES
    PROFILE_STORAGES = {k: os.path.join(
        v, "saves/profile") for k, v in utils.STORAGES.items()}
    PROFILE_EXISTING = {}
    # this first loop defines configuration order
    priority_paths = utils.storage_order()
    priority_paths.reverse()
    for token in priority_paths:  # reverse order (overriding)
        PROFILE_EXISTING[token] = []
        for pfile in glob.glob(os.path.join(PROFILE_STORAGES[token], "*.yml")):
            PROFILE_EXISTING[token].append(
                (os.path.basename(pfile)[:-4], pfile))


def list_profiles(scope=None):
    assert (scope in PROFILE_STORAGES.keys() or scope is None)
    if scope is None:
        return PROFILE_EXISTING
    else:
        return PROFILE_EXISTING[scope]


class Profile:
    def __init__(self, name, scope=None):
        utils.check_valid_scope(scope)
        self._name = name
        self._scope = scope
        self._details = {}
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
        self._file = os.path.join(PROFILE_STORAGES[self._scope], self._name + ".yml")
        self._exists = False

    def fill(self, raw):
        # some checks
        assert (isinstance(raw, dict))
        check = [val for val in config.CONFIG_BLOCKS if val in raw.keys()]
        if len(check) != len(config.CONFIG_BLOCKS):
            log.err(
                "All {} configuration blocks are required to build "
                "a valid profile!".format(len(config.CONFIG_BLOCKS)))

        # fill is called either from 'build' (dict of configurationBlock)
        # of from 'clone' (dict of raw file inputs)
        for k, v in raw.items():
            if isinstance(v, config.ConfigurationBlock):
                self._details[k] = v.dump()
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
            log.err("Invalid profile name {}".format(self._name))
        self._retrieve_file()

        if not os.path.isfile(self._file):
            log.err("Internal Error: file {} not found!".format(self._file))
        
        log.info("load {} ({})".format(self._name, self._scope))
        with open(self._file) as f:
            self._details = Dict(yaml.safe_load(f))

    def load_template(self):
        self._exists = True
        self._file = os.path.join(
                    ROOTPATH,
                    'templates/profile-format.yml')
        with open(self._file, 'r') as fh:
            self.fill(yaml.load(fh, Loader=yaml.FullLoader))

    def check(self, fail=True):
        for kind in config.CONFIG_BLOCKS:
            if kind not in self._details:
                raise jsonschema.exceptions.ValidationError("Missing '{}' in profile".format(kind))
            utils.ValidationScheme(kind).validate(self._details[kind], fail)
    

    def flush_to_disk(self):
        self._retrieve_file()
        self.check()

        # just in case the block subprefix does not exist yet
        prefix_file = os.path.dirname(self._file)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)

        with open(self._file, 'w') as f:
            yaml.safe_dump(self._details, f)

    def clone(self, clone):
        self._retrieve_file()
        log.info("Compute target prefix: {}".format(self._file))
        assert(not os.path.isfile(self._file))
        self._details = clone._details

    def delete(self):
        log.info("delete {}".format(self._file))
        os.remove(self._file)
        pass

    def display(self):
        log.print_header("Profile View")
        log.print_section("Scope: {}".format(self._scope.capitalize()))
        log.print_section("Profile details:")
        if self._details:
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
            prefix="{}".format(self.full_name),
            suffix=".yml"
        )
        fplugin = tempfile.NamedTemporaryFile(
            mode='w+',
            prefix="{}".format(self.full_name),
            suffix=".py"
        )
        with open(self._file, 'r') as f:
            stream = yaml.load(f, Loader=yaml.FullLoader)
            if stream:
                yaml.dump(stream, fname)

            if stream and 'plugin' in stream['runtime']:
                content = base64.b64decode(stream['runtime']['plugin']).decode('ascii')
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
            utils.open_in_editor(fname.name, fplugin.name, e=e)
        except:
            log.warn("Issue with opening the conf. block. Stop!")
            return
        
        # reset cursors
        fname.seek(0)
        fplugin.seek(0)

        #now, dump back temp file to the original saves
        stream = yaml.load(fname, Loader=yaml.FullLoader)
        if stream is None:
            stream = dict()
        stream_plugin = fplugin.read()
        if len(stream_plugin) > 0:
            stream['runtime']['plugin'] = base64.b64encode(stream_plugin.encode('ascii'))

        #just check the outcome is valid
        self.fill(stream)
        try:
            self.check(fail=False)
        except jsonschema.exceptions.ValidationError as e:
            with tempfile.NamedTemporaryFile(mode="w+", suffix=".yml.rej", prefix=self.full_name, delete=False) as rej_fh:
                yaml.dump(stream, rej_fh)
            
                log.err("Invalid format: {}".format(e.message),
                        "Rejected file: {}".format(rej_fh.name),
                        "You may use 'pcvs check' to validate external resource",
                        "before the importation.")

        with open(self._file, 'w') as f:
            yaml.dump(stream, f)

        # delete temp files (replace by 'with...' ?)
        fname.close()
        fplugin.close()
        
        self.load_from_disk()
    
    def split_into_configs(self, prefix, blocklist=config.CONFIG_BLOCKS, scope=None):
        objs = list()
        if 'all' in blocklist:
            blocklist = config.CONFIG_BLOCKS
        if scope is None:
            scope = self._scope

        for name in blocklist:
            c = config.ConfigurationBlock(name, prefix, scope)
            if c.is_found():
                log.err("{} already exist!".format(c.full_name))
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
