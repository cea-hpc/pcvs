from pcvs.helpers import log


def identify(pm_node):
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

    def get(self, load, install):
        pass

    def install(self):
        return


class SpackManager(PManager):
    def __init__(self, spec):
        super().__init__(spec)
        self.spec = spec

    def get(self, load=True, install=True):
        s = list()
        if install:
            s.append("spack install {}".format(self.spec))
        if load:
            s.append("eval `spack load --sh {}`".format(self.spec))
        return "\n".join(s)


class ModuleManager(PManager):
    def __init__(self, spec):
        super().__init__(spec)
        self.spec = spec

    def get(self, load=True, install=False):
        s = ""
        # 'install' does not mean anything here
        if load:
            s += "module load {}".format(self.spec)
        return s
