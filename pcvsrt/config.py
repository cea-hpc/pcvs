import yaml
import os
from pcvsrt.utils import logs


PREFIXPATH = "../.."
BASEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), PREFIXPATH))
CONFPATHS = {
    'global': BASEPATH + "/share/saves/",
    'user': os.environ['HOME'] + "/.pcvsrt/saves/",
    'local': os.getcwd() + "/.pcvsrt/saves/"
}

CONFIG_BLOCKS = ['compiler', 'runtime', 'machine', 'criterion', 'group']

def check_valid_subgroup_name(s):
    if s not in CONFIG_BLOCKS:
        logs.err("Invalid SUBGROUP '{}'".format(s),
                 "See --help for more information",
                 abort=1)


class ConfigurationBlock:
    def __init__(self, configType):
        check_valid_subgroup_name(configType)
        self._type = configType
        self._files = {}
        self._files['global'] = ConfigurationBlock.list_config_files("global", configType)
        self._files['user'] = ConfigurationBlock.list_config_files("user", configType)
        self._files['local'] = ConfigurationBlock.list_config_files("local", configType)

        self._alias = {}
        for (name, path) in self._files['global']:
            self._alias[name] = path
        for (name, path) in self._files['user']:
            self._alias[name] = path
        for (name, path) in self._files['local']:
            self._alias[name] = path

    def get_file_from_name(self, name, scope=None):
        if scope is None:
            return self._alias[name]
        else:
            return self._files[scope]

    def get_type(self):
        return self._type

    def get_configs(self):
        return self._files

    @staticmethod
    def list_config_files(scope, subpath):
        prefix = os.path.join(CONFPATHS[scope], subpath)
        if prefix:
            return {os.path.basename(elt): elt for elt in os.listdir(prefix)}
