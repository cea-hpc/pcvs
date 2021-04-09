import os
import pprint

import yaml
import jsonschema
from addict import Dict

import pcvs
from pcvs import NAME_SRCDIR, NAME_BUILDIR, PATH_INSTDIR
from pcvs.helpers import log, package_manager, utils


####################################
####   YAML VALIDATION OBJECT   ####
####################################
class ValidationScheme:
    avail_list = None

    @classmethod
    def available_schemes(cls):

        if cls.avail_list is None:
            cls.avail_list = list()
            for f in os.listdir(os.path.join(PATH_INSTDIR, 'schemes/')):
                cls.avail_list.append(f.replace('-scheme.yml', ''))
        
        return cls.avail_list

    def __init__(self, name):
        self._prefix = name

        with open(os.path.join(
                            PATH_INSTDIR,
                            'schemes/{}-scheme.yml'.format(name)
                        ), 'r') as fh:
            self._scheme = yaml.load(fh, Loader=yaml.FullLoader)

    def validate(self, content, fail_on_error=True, filepath=None):
        try:
            if filepath is None:
                filepath = "'data stream'"
            
            jsonschema.validate(instance=content, schema=self._scheme)
        except jsonschema.exceptions.ValidationError as e:
            if fail_on_error:
                log.err("Wrong format: {} ('{}'):".format(
                                filepath,
                                self._prefix),
                        "{}".format(e.message))
            else:
                raise e
        except Exception as e:
            log.err(
                "Something wrong happen validating {}".format(self._prefix),
                '{}'.format(e)
            )


class Config(Dict):
    def __init__(self, d={}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for n in d:
            self.__setitem__(n, d[n])
    
    def validate(self, kw, fail_on_error=True):
        assert(kw in ValidationScheme.available_schemes())
        ValidationScheme(kw).validate(self)

    def __setitem__(self, param, value):
        if isinstance(value, dict):
            value = Dict(value)
        super().__setitem__(param, value)

    def set_ifdef(self, k, v):
        if v is not None:
            self[k] = v

    def set_nosquash(self, k, v):
        if not self.isset(k):
            self[k] = v

    def isset(self, k):
        return k in self
    
    def to_dict(self):
        # this dirty hack is due to a type(self) used into addict.py
        # leading to misconvert derived classes from Dict()
        # --> to_dict() checks if a sub-value is instance of type(self)
        # In our case here, type(self) return Config(), addict not converting
        # sub-Dict() into dict(). This double call to to_dict() seems
        # to fix the issue. But an alternative to addict should be used
        # (customly handled ?)
        copy = Dict(super().to_dict())
        return copy.to_dict()

    def from_dict(self, d):
        for k, v in d.items():
            self[k] = v
    
    def from_file(self, filename):
        with open(filename, 'r') as fh:
            d = yaml.safe_load(fh)
        self.from_dict(d)


class MetaConfig(Dict):
    root = None
    validation_default_file = pcvs.PATH_VALCFG
    
    def __init__(self, base={}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(base, dict):
            for k, v in base.items():
                self[k] = v
        self['__internal'] = Config()

    def __setitem__(self, param, value):
        assert(isinstance(value, Config))
        super().__setitem__(param, value)

    def bootstrap_generic(self, subnode, node):
        #self.setdefault(subnode, Config())
        if subnode not in self:
            self[subnode] = Config()
        
        for k, v in node.items():
            self[subnode][k] = v
        self[subnode].validate(subnode)
        return self[subnode]

    def bootstrap_compiler(self, node):
        subtree = self.bootstrap_generic('compiler', node)
        if 'package_manager' in subtree:
            self.set_internal('cc_pm', package_manager.identify(subtree.package_manager))
        return subtree

    def bootstrap_runtime(self, node):
        subtree = self.bootstrap_generic('runtime', node)
        if 'package_manager' in subtree:
            self.set_internal('rt_pm', package_manager.identify(subtree.package_manager))
        return subtree
    
    def bootstrap_group(self, node):
        return self.bootstrap_generic('group', node)

    def bootstrap_validation_from_file(self, filepath):
        node = Dict()
        if filepath is None:
            filepath = self.validation_default_file

        if os.path.isfile(filepath):
            try:
                with open(filepath, 'r') as fh:
                    node = Dict(yaml.load(fh, Loader=yaml.FullLoader))
            except (IOError, yaml.YAMLError):
                log.err("Error(s) found while loading (}".format(filepath))
        
        return self.bootstrap_validation(node)

    def bootstrap_validation(self, node):
        subtree = self.bootstrap_generic('validation', node)

        # #### now set default value ####
        subtree.set_nosquash('verbose', 0)
        subtree.set_nosquash('color', True)
        subtree.set_nosquash('pf_name', 'default')
        subtree.set_nosquash('output', os.path.join(os.getcwd(), NAME_BUILDIR))
        subtree.set_nosquash('background', False)
        subtree.set_nosquash('override', False)
        subtree.set_nosquash('dirs', '.')
        subtree.set_nosquash('xmls', list())
        subtree.set_nosquash('simulated', False)
        subtree.set_nosquash('anonymize', False)
        subtree.set_nosquash('exported_to', None)
        subtree.set_nosquash('reused_build', None)
        subtree.set_nosquash('result', {"format": ['json']})
        subtree.set_nosquash('author', {
            "name": utils.get_current_username(),
            "email": utils.get_current_usermail()})

        # Annoying here:
        # self.result should be allowed even without the 'set_ifnot' above
        # but because of inheritance, it does not result as a Dict()
        # As the 'set_ifnot' is required, it is solving the issue
        # but this corner-case should be remembered as it WILL happen again :(
        if 'format' not in subtree.result:
            subtree.result.format = ['json']
        if 'log' not in subtree.result:
            subtree.result.log = 1
        if 'logsz' not in subtree.result:
            subtree.result.logsz = 1024
        
        return subtree

    def bootstrap_machine(self, node):
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
        
        #redirect to direct programs if no wrapper is defined
        for kind in ['allocate', 'run', 'batch']:
            if not subtree.job_manager[kind].wrapper and subtree.job_manager[kind].program:
                subtree.job_manager[kind].wrapper = subtree.job_manager[kind].program
        return subtree

    def bootstrap_criterion(self, node):
        return self.bootstrap_generic('criterion', node)

    def set_internal(self, k, v):
        self['__internal'][k] = v

    def get_internal(self, k):
        if k in self['__internal']:
            return self['__internal'][k]
        else:
            return None

    def dump_for_export(self):
        res = Dict()
        for k, v in self.items():
            if k == '__internal':
                continue
            # should ignore __internal
            res[k] = v.to_dict()
        
        return res.to_dict()

