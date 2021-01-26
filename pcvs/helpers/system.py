import os
import pprint

import yaml
from addict import Dict

from pcvs import BACKUP_NAMEDIR, BUILD_NAMEDIR
from pcvs.helpers import log, package_manager, utils


class CfgBase(Dict):
   
    def __init__(self, node, *args, **kwargs):
        super().__init__(*args, **kwargs)

        assert(isinstance(node, dict))

        for n in node:
            self.__setitem__(n, node[n])

    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        super().__setitem__(param, value)

    def override(self, key, value):
        if value is not None:
            self.__setitem__(key, value)

    def set_ifnot(self, key, value):
        if not self.isset(key):
            self.__setitem__(key, value)

    def isset(self, k):
        return k in self

    def serialize(self):
        return self.to_dict()


class CfgCompiler(CfgBase):
    def __init__(self, node):
        super().__init__(node)
        if 'package_manager' in self:
            self.obj = package_manager.identify(self.package_manager)


class CfgRuntime(CfgBase):
    def __init__(self, node):
        super().__init__(node)
        if 'package_manager' in self:
            self.obj = package_manager.identify(self.package_manager)


class CfgMachine(CfgBase):
    def __init__(self, node):
        super().__init__(node)
        #now, sanity checks
        self.set_ifnot('name', 'default')
        self.set_ifnot('nodes', 1)
        self.set_ifnot('cores_per_node', 1)
        self.set_ifnot('concurrent_run', 1)

        if 'default_partition' not in self or 'partitions' not in self:
            return

        # override default values by selected partition
        for elt in self.partitions:
            if elt.get('name', self.default_partition) == self.default_partition:
                self.update(elt)
                break
        
        #redirect to direct programs if no wrapper is defined
        for kind in ['allocate', 'run', 'batch']:
            if not self.job_manager[kind].wrapper and self.job_manager[kind].program:
                self.job_manager[kind].wrapper = self.job_manager[kind].program


class CfgCriterion(CfgBase):
    def __init__(self, node):
        super().__init__(node)


class CfgTemplate(CfgBase):
    def __init__(self, node):
        super().__init__(node)


class CfgValidation(CfgBase):
    default_valfile = os.path.join(os.environ['HOME'], BACKUP_NAMEDIR, "validation.yml")

    def get_valfile(override):
        if override is None:
            override = CfgValidation.default_valfile
        return override

    def __init__(self, filename=None):
        node = Dict()
        if filename is None:
            filename = CfgValidation.default_valfile

        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fh:
                    node = Dict(yaml.load(fh, Loader=yaml.FullLoader))
            except (IOError, yaml.YAMLError):
                log.err("Error(s) found while loading (}".format(filename))

        super().__init__(node)

        utils.ValidationScheme('settings').validate(self)

        # #### now set default value ####
        self.set_ifnot('verbose', 0)
        self.set_ifnot('color', True)
        self.set_ifnot('pf_name', 'default')
        self.set_ifnot('output', os.path.join(os.getcwd(), BUILD_NAMEDIR))
        self.set_ifnot('background', False)
        self.set_ifnot('override', False)
        self.set_ifnot('dirs', '.')
        self.set_ifnot('xmls', list())
        self.set_ifnot('simulated', False)
        self.set_ifnot('anonymize', False)
        self.set_ifnot('exported_to', None)
        self.set_ifnot('reused_build', None)
        self.set_ifnot('result', {"format": ['json']})
        self.set_ifnot('author', {
            "name": utils.get_current_username(),
            "email": utils.get_current_usermail()})

        # Annoying here:
        # self.result should be allowed even without the 'set_ifnot' above
        # but because of inheritance, it does not result as a Dict()
        # As the 'set_ifnot' is required, it is solving the issue
        # but this corner-case should be remembered as it WILL happen again :(

        if 'format' not in self.result:
            self.result.format = ['json']
        if 'log' not in self.result:
            self.result.log = 1
        if 'logsz' not in self.result:
            self.result.logsz = 1024
        
    def override(self, k, v):
        if k == 'output' and v is not None:
            os.path.join(os.path.abspath(v), BUILD_NAMEDIR)
        CfgBase.override(self, k, v)


class Settings(Dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        super().__setitem__(param, value)

    def serialize(self):
        return Dict(self).to_dict()


sysTable = None


def save_as_global(obj):
    global sysTable
    assert(isinstance(obj, Settings))
    sysTable = obj


def get(cat=None):
    if cat is not None:
        if cat not in sysTable:
            sysTable[cat] = Dict()
        return sysTable[cat]
    return sysTable
