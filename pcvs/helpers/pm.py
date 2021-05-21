def identify(pm_node):
    """identifies where 

    :param pm_node: [description]
    :type pm_node: [type]
    :return: [description]
    :rtype: [type]
    """
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
    """generic Package Manager
    """

    def __init__(self, spec=None):
        """constructor for PManager object

        :param spec: specifications for this Package Manager, defaults to None
        :type spec: str, optional
        """
        pass

    def get(self, load, install):
        """Get specified packages for this manager

        :param load: True to load the package
        :type load: bool
        :param install: True to install the package
        :type install: bool
        """
        pass

    def install(self):
        """install specified packages
        """
        return


class SpackManager(PManager):
    """handles Spack package manager
    """

    def __init__(self, spec):
        """constructor for SpackManager object

        :param spec: specifications for Spack manager
        :type spec: str
        """
        super().__init__(spec)
        self.spec = spec

    def get(self, load=True, install=True):
        """get the commands to install the specified package

        :param load: load the specified package, defaults to True
        :type load: bool, optional
        :param install: install the specified package, defaults to True
        :type install: bool, optional
        :return: command to install/load the package
        :rtype: str
        """
        s = list()
        if install:
            s.append("spack install {}".format(self.spec))
        if load:
            s.append("eval `spack load --sh {}`".format(self.spec))
        return "\n".join(s)


class ModuleManager(PManager):
    """handles Module package manager"""

    def __init__(self, spec):
        """constructor for Module package manager

        :param spec: specifications for Module manager
        :type spec: str
        """
        super().__init__(spec)
        self.spec = spec

    def get(self, load=True, install=False):
        """get the command to install the specified package

        :param load: load the specified package, defaults to True
        :type load: bool, optional
        :param install: install the specified package, defaults to False
        :type install: bool, optional
        :return: command to install/load the package
        :rtype: str
        """
        s = ""
        # 'install' does not mean anything here
        if load:
            s += "module load {}".format(self.spec)
        return s
