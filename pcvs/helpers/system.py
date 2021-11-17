import os

import addict
import jsonschema
from ruamel.yaml import YAML, YAMLError

import pcvs
from pcvs import NAME_BUILDIR, PATH_INSTDIR
from pcvs.helpers import git, pm
from pcvs.helpers.exceptions import CommonException, ValidationException


####################################
####   YAML VALIDATION OBJECT   ####
####################q################
class ValidationScheme:
    """Object manipulating schemes (yaml) to enforce data formats.
    A validationScheme is instancied according to a 'model' (the format to
    validate). This instance can be used multiple times to check multiple 
    streams belonging to the same model.
    """
    avail_list = None

    @classmethod
    def available_schemes(cls):
        """return list of currently supported formats to be validated. The list
        is extracted from INSTALL/schemes/<model>-scheme.yml
        """
        if cls.avail_list is None:
            cls.avail_list = list()
            for f in os.listdir(os.path.join(PATH_INSTDIR, 'schemes/')):
                cls.avail_list.append(f.replace('-scheme.yml', ''))

        return cls.avail_list

    def __init__(self, name):
        """Create a new ValidationScheme instancen based on a given model.
            During initialisatio, the file scheme is loaded from disk.
            :raises:
            ValidationException.SchemeError: file is not found OR unable to load
            the YAML scheme file.
        """
        self._name = name

        try:
            with open(os.path.join(
                    PATH_INSTDIR,
                    'schemes/{}-scheme.yml'.format(name)), 'r') as fh:
                self._scheme = YAML(typ='safe').load(fh)
        except (IOError, YAMLError):
            raise ValidationException.SchemeError(
                "Unable to load scheme {}".format(name))

    def validate(self, content, filepath=None):
        """Validate a given datastructure (dict) agasint the loaded scheme.

            :param content: json to validate
            :type content: dict
            :param filepath: 
            :raises ValidationException.FormatError: data are not valid
            :raises ValidationException.SchemeError: issue while applying scheme
        """
        try:
            if filepath is None:
                filepath = "'data stream'"

            jsonschema.validate(instance=content, schema=self._scheme)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationException.FormatError(
                "Scheme '{}' failed to verify the following file:\n{}".format(
                    self._name, filepath),
                reason=e.message)
        except jsonschema.exceptions.SchemaError as e:
            raise ValidationException.SchemeError(
                name=self._name,
                content=self._scheme,
                error=e)


class MetaDict(addict.Dict):
    """Helps with managing large configuration sets, based on dictionaries.

    Once instanciated, an arbitraty subnode can be initialized like:

        o = MetaDict()
        o.field_a.subnode2 = 4

    Currently, this class is just derived from addict.Dict. It is planned to
    remove this adherence.
    """

    def to_dict(self):
        """Convert the object to a regular dict.

        :return: a regular Python dict
        :rtype: Dict
        """
        return super().to_dict()


class Config(MetaDict):
    """a 'Config' is a dict extension (an MetaDict), used to manage all
    configuration fields. While it can contain arbitrary data, the whole PCVS
    configuration is composed of 5 distinct 'categories', each being a single
    Config. These are then gathered in a `MetaConfig` object (see below)
    """

    def __init__(self, d={}, *args, **kwargs):
        """Init the object and propagate properly the init to MetaDict() object
        :param d: items of the configuration
        :type d: dict
        :param *arg: items of the configuration
        :type *arg: tuple
        :param **kwargs: items of the configuration
        :type **kwargs: dict"""
        super().__init__(*args, **kwargs)
        for n in d:
            self.__setitem__(n, d[n])

    def validate(self, kw):
        """Check if the Config instance matches the expected format as declared
        in schemes/. As the 'category' is not carried by the object itself, it
        is provided by the function argument.

        :param kw: keyword describing the configuration to be validated (scheme)
        :type kw: str
        """
        assert(kw in ValidationScheme.available_schemes())
        ValidationScheme(kw).validate(self)

    def __setitem__(self, param, value):
        """extend it to handle dict initialization (needs MetaDict conversion)
        :param param: name of value to add to configuration
        :type param: str
        :param value: value to add to configuration
        :type value: object"""
        if isinstance(value, dict):
            value = MetaDict(value)
        super().__setitem__(param, value)

    def set_ifdef(self, k, v):
        """shortcut function: init self[k] only if v is not None
        :param k: name of value to add
        :type k: str
        :param v: value to add
        :type v: str"""
        if v is not None:
            self[k] = v

    def set_nosquash(self, k, v):
        """shortcut function: init self[k] only if v is not already set
        :param k: name of value to add
        :type k: str
        :param v: value to add
        :type v: str"""
        if not self.isset(k):
            self[k] = v

    def isset(self, k):
        """check key existence in config dict
        :param k: name of param to check
        :type k: str"""
        return k in self

    def to_dict(self):
        """Convert the Config() to regular dict."""
        # this dirty hack is due to a type(self) used into addict.py
        # leading to misconvert derived classes from Dict()
        # --> to_dict() checks if a sub-value is instance of type(self)
        # In our case here, type(self) return Config(), addict not converting
        # sub-Dict() into dict(). This double call to to_dict() seems
        # to fix the issue. But an alternative to addict should be used
        # (customly handled ?)
        copy = MetaDict(super().to_dict())
        return copy.to_dict()

    def from_dict(self, d):
        """Fill the current Config from a given dict
        :param d: dictionary to add
        :type d: dict"""
        for k, v in d.items():
            self[k] = v

    def from_file(self, filename):
        """Fill the current config from a given file

            :raises CommonException.IOError: file does not exist OR badly formatted
        """
        try:
            with open(filename, 'r') as fh:
                d = YAML(typ='safe').load(fh)
                self.from_dict(d)
        except (IOError, YAMLError) as e:
            raise CommonException.IOError(
                "{} invalid or badly formatted".format(filename))


class MetaConfig(MetaDict):
    """Root configuration object. It is composed of Config(), categorizing
    each configuration blocks. This MetaConfig() contains the whole profile
    along with any validation and current run information.
    This configuration is used as a dict extension.

    To avoid carrying a global instancied object over the whole code, a
    class-scoped attribute allows to browse the global configuration from
    anywhere through `Metaconfig.root`"
    """
    root = None
    validation_default_file = pcvs.PATH_VALCFG

    def __init__(self, *args, **kwargs):
        """constructor method.

        :param args: list of positional arguments
        :type args: tuple
        :param kwargs: list of keyword-based arguments
        """
        super().__init__(*args, **kwargs)

        # The 'internal' node is a special one. Put here anything not requiring
        # to be published (like conf.yml, etc...). mainly one-time Python
        # objects
        if '__internal' not in self:
            self['__internal'] = Config()

    def __setitem__(self, param, value):
        """Extend the default MetaDict setter mthod to reach the base class one"""
        super().__setitem__(param, value)

    def bootstrap_generic(self, subnode, node):
        """"Initialize a Config() object and store it under name 'node'
        :param subnode: node name
        :type subnode: str
        :param node: node to initialize and add
        :type node: dict
        :return: added subnode
        :rtype: dict"""

        if subnode not in self:
            self[subnode] = Config()

        for k, v in node.items():
            self[subnode][k] = v

        self[subnode].validate(subnode)
        return self[subnode]

    def bootstrap_compiler(self, node):
        """"Specific initialize for compiler config block
        :param node: compiler block to initialize
        :type node: dict
        :return: added node
        :rtype: dict"""
        subtree = self.bootstrap_generic('compiler', node)
        if 'package_manager' in subtree:
            self.set_internal('cc_pm', pm.identify(subtree.package_manager))
        return subtree

    def bootstrap_runtime(self, node):
        """"Specific initialize for runtime config block
        :param node: runtime block to initialize
        :type node: dict
        :return: added node
        :rtype: dict"""
        subtree = self.bootstrap_generic('runtime', node)
        if 'package_manager' in subtree:
            self.set_internal('rt_pm', pm.identify(subtree.package_manager))
        return subtree

    def bootstrap_group(self, node):
        """"Specific initialize for group config block.
        There is currently nothing to here but calling bootstrap_generic()
        :param node: runtime block to initialize
        :type node: dict
        :return: added node
        :rtype: dict
        """
        return self.bootstrap_generic('group', node)

    def bootstrap_validation_from_file(self, filepath):
        """Specific initialize for validation config block. This function loads
            a file containing the validation dict.

            :param filepath: path to file to be validated
            :type filepath: os.path, str
            :raises CommonException.IOError: file is not found or badly 
                formatted
        """
        node = MetaDict()
        if filepath is None:
            filepath = self.validation_default_file

        if os.path.isfile(filepath):
            try:
                with open(filepath, 'r') as fh:
                    node = MetaDict(YAML(typ='safe').load(fh))
            except (IOError, YAMLError) as e:
                raise CommonException.IOError(
                    "Error(s) found while loading (}".format(filepath))

        # some post-actions
        for field in ["output", "reused_build", "runlog"]:
            if field in node:
                node[field] = os.path.abspath(node[field])

        if node.dirs:
            node.dirs = {k: os.path.abspath(v) for k, v in node.dirs.items()}

        return self.bootstrap_validation(node)

    def bootstrap_validation(self, node):
        """"Specific initialize for validation config block
        :param node: validation block to initialize
        :type node: dict
        :return: initialized node
        :rtype: dict"""
        subtree = self.bootstrap_generic('validation', node)

        # Initialize default values when not set by user or default files
        subtree.set_nosquash('verbose', 0)
        subtree.set_nosquash('color', True)
        subtree.set_nosquash('default_profile', 'default')
        subtree.set_nosquash('output', os.path.join(os.getcwd(), NAME_BUILDIR))
        subtree.set_nosquash('background', False)
        subtree.set_nosquash('override', False)
        subtree.set_nosquash('dirs', None)
        subtree.set_nosquash('runlog', os.path.join(subtree.output, 'out.log'))
        subtree.set_nosquash('simulated', False)
        subtree.set_nosquash('anonymize', False)
        subtree.set_nosquash('onlygen', False)
        subtree.set_nosquash('timeout', None)
        subtree.set_nosquash('target_bank', None)
        subtree.set_nosquash('reused_build', None)
        subtree.set_nosquash('webreport', None)
        subtree.set_nosquash(
            'buildcache', os.path.join(subtree.output, 'cache'))
        subtree.set_nosquash('result', {"format": ['json']})
        subtree.set_nosquash('author', {
            "name": git.get_current_username(),
            "email": git.get_current_usermail()})

        # Annoying here:
        # self.result should be allowed even without the 'set_nosquash' above
        # but because of inheritance, it does not result as a MetaDict()
        # As the 'set_nosquash' is required, it is solving the issue
        # but this corner-case should be remembered as it WILL happen again :(
        if 'format' not in subtree.result:
            subtree.result.format = ['json']
        if 'log' not in subtree.result:
            subtree.result.log = 1
        if 'logsz' not in subtree.result:
            subtree.result.logsz = 1024

        return subtree

    def bootstrap_machine(self, node):
        """"Specific initialize for machine config block
        :param node: machine block to initialize
        :type node: dict
        :return: initialized node
        :rtype: dict"""
        subtree = self.bootstrap_generic('machine', node)
        subtree.set_nosquash('name', 'default')
        subtree.set_nosquash('nodes', 1)
        subtree.set_nosquash('cores_per_node', 1)
        subtree.set_nosquash('concurrent_run', 1)

        if 'default_partition' not in subtree or 'partitions' not in subtree:
            return

        # override default values by selected partition
        for elt in subtree.partitions:
            if elt.get('name', subtree.default_partition) == subtree.default_partition:
                subtree.update(elt)
                break

        # redirect to direct programs if no wrapper is defined
        for kind in ['allocate', 'run', 'batch']:
            if not subtree.job_manager[kind].wrapper and subtree.job_manager[kind].program:
                subtree.job_manager[kind].wrapper = subtree.job_manager[kind].program
        return subtree

    def bootstrap_criterion(self, node):
        """"Specific initialize for criterion config block
        :param node: criterion block to initialize
        :type node: dict
        :return: initialized node
        :rtype: dict"""
        return self.bootstrap_generic('criterion', node)

    def set_internal(self, k, v):
        """manipulate the internal MetaConfig() node to store not-exportable data
        :param k: name of value to add
        :type k: str
        :param v: value to add
        :type v: str"""
        self['__internal'][k] = v

    def get_internal(self, k):
        """manipulate the internal MetaConfig() node to load not-exportable data
        :param k: value to get
        :type k: str"""
        if k in self['__internal']:
            return self['__internal'][k]
        else:
            return None

    def dump_for_export(self):
        """Export the whole configuration as a dict. Prune any __internal node
        beforehand.
        """
        res = MetaDict()
        for k, v in self.items():
            if k == '__internal':
                continue
            # should ignore __internal
            res[k] = v.to_dict()

        return res.to_dict()
