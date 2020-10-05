from pcvsrt.helpers import log

def identify_manager(pm_node):
    ret = list()
    if 'spack' in pm_node:
        if not isinstance(pm_node['spack'], list):
            pm_node['spack'] = [pm_node['spack']]
        for elt in pm_node['spack']:
            ret.append(SpackManager(elt))
    
    if 'module' in pm_node:
        if not isinstance(pm_node['module'], list):
            pm_node['module'] = [pm_node['module']]
        for elt in pm_node['module']:
            ret.append(ModuleManager(elt))

    return ret


class PManager:
    def __init__(self, spec):
        pass

    def loadenv(self):
        pass


class SpackManager(PManager):
    def __init__(self, spec):
        super().__init__(spec)
        self.spec = spec

    def loadenv(self):
        return "eval `spack load --sh {}`".format(self.spec)


class ModuleManager(PManager):
    def __init__(self, spec):
        super().__init__(spec)
        self.spec = spec

    def loadenv(self):
        return "module load {}".format(self.spec)
