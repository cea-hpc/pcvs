from addict import Dict
import os
import yaml
import pprint

from pcvsrt.helpers import log, pm, validation


class CfgBase(Dict):
   
    def __init__(self, param, *args, **kwargs):
        super().__init__(*args, **kwargs)
        preset = None
        if isinstance(param, str) and os.path.isfile(param):
            try:
                with open(param, 'r') as fh:
                    preset = yaml.load(fh, Loader=yaml.FullLoader)

            except (IOError, yaml.YAMLError):
                log.err("Error(s) found while load (}".format(param))
        else:
            preset = param

        for n in preset:
            self.__setitem__(n, preset[n])

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
            self.obj = pm.identify_manager(self.package_manager)


class CfgRuntime(CfgBase):
    def __init__(self, node):
        super().__init__(node)
        if 'package_manager' in self:
            self.obj = pm.identify_manager(self.package_manager)


class CfgMachine(CfgBase):
    def __init__(self, node):
        super().__init__(node)
        #now, sanity checks
        self.set_ifnot('nodes', 1)
        self.set_ifnot('cores_per_node', 1)
        self.set_ifnot('concurrent_run', 1)

        if 'default' not in self:
            return

        # override default values by selected partition
        override_node = [v for d in self.partitions for k, v in d.items() if k == self.default]
        self.update(override_node[0])


class CfgCriterion(CfgBase):
    def __init__(self, node):
        super().__init__(node)


class CfgTemplate(CfgBase):
    def __init__(self, node):
        super().__init__(node)


class CfgValidation(CfgBase):
    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.join(os.environ['HOME'], ".pcvsrt/validation.yml")
        super().__init__(filename)

        validation.ValidationScheme('settings').validate(self)

        # #### now set default value ####
        self.set_ifnot('verbose', 0)
        self.set_ifnot('color', True)
        self.set_ifnot('pf_name', 'default')
        self.set_ifnot('output', os.path.join(os.getcwd(), ".pcvs"))
        self.set_ifnot('background', False)
        self.set_ifnot('override', False)
        self.set_ifnot('dirs', '.')
        self.set_ifnot('xmls', list())
        self.set_ifnot('simulated', False)
        self.set_ifnot('anonymize', False)
        self.set_ifnot('exported_to', None)

        if 'format' not in self.result:
            self.result.formats = ['json']
        if 'log' not in self.result:
            self.result.log = 2
        if 'logsz' not in self.result:
            self.result.logsz = 1024
        
    def override(self, k, v):
        if k == 'output' and v is not None:
            os.path.join(os.path.abspath(v), ".pcvs")
        CfgBase.override(self, k, v)


class Settings(Dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        super().__setitem__(param, value)

    def serialize(self):
        return self.to_dict()


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
