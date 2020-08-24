from pcvsrt import logs, helper
import yaml
from addict import Dict
import itertools
import pprint

def xml_setif(elt, k, tag=None):
    if tag is None:
        tag = k
    if k in elt.keys() and elt[k] is not None:
        if isinstance(elt[k], list):
            return "".join(["<"+tag+">"+helper.xml_escape(str(i))+"</"+tag+">" for i in elt[k]])
        else:
            return "<"+tag+">"+helper.xml_escape(str(elt[k]))+"</"+tag+">"
    else:
        return ""




def unfold_sequence(x, sys=None):
    return x


class Test:
    def __init__(self, **kwargs):
        self._array = kwargs
    
    def serialize(self):
        string = "<job>"
        string += "{}".format(xml_setif(self._array, 'name'))
        string += "{}".format(xml_setif(self._array, 'command'))
        string += "<deps>{}</deps>".format(xml_setif(self._array, 'dep'))
        string += "{}".format(xml_setif(self._array, "rc"))
        string += "{}".format(xml_setif(self._array, 'time'))
        string += "{}".format(xml_setif(self._array, 'delta'))
        string += "{}".format(xml_setif(self._array, 'resources'))
        string += "{}".format(xml_setif(self._array, 'extras'))
        string += "{}".format(xml_setif(self._array, 'postscript'))
        string += "<constraints>{}</constraints>".format(xml_setif(self._array, 'constraint'))
        string += "</job>"
        return string


class TEDescriptor(yaml.YAMLObject):
    @classmethod
    def init_system_wide(cls, crit, base_it):
        cls._sys_crit = Dict(crit)
        cls._base_it = base_it
    
    def __init__(self, node, pkg, name):
        if not isinstance(node, dict):
            logs.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._te_name = name
        self._te_pkg = pkg
        self._node = Dict(node)
        self._full_name = ".".join([pkg, name])
        self._criterion = Dict()
        self._override = self.__refine_iterators()

    def __refine_iterators(self):
        if 'iterate' not in self._node:
            self._criterion = self._sys_crit
            return False
        te_it = self._node.iterate
        for k_it, v_redefine in te_it.items():
            # special case: 'program' it
            if 'program' == k_it:
                logs.warn("TODO: handle custom program iterators")
            elif k_it not in self._sys_crit.keys():
                logs.warn("criterion '{}' not found. Discard".format(k_it))
            else:
                values = unfold_sequence(v_redefine['values'], self._sys_crit[k_it])
                # intereset values set
                final_set = set(values) | self._sys_crit[k_it]['values']
                if not final_set:
                    logs.warn("No valid intersection found for '{}, Discard".format(k_it))
                else:
                    self._criterion.k_it = (final_set)
        return True

    @property
    def name(self):
        return self._name

    def has_build_rule(self):
        return self._node['build']

    def __build_from_sources(self):
        command = list()
        build_node = self._node.build
        lang = helper.detect_source_lang(build_node.files)
        command.append(helper.prepare_cmd_build_prefix(lang, build_node.variants))
        command.append('{}'.format(build_node.get('cflags', '')))
        command.append('{}'.format(" ".join([build_node.files])))
        command.append('{}'.format(build_node.get('ldflags', '')))

        if 'binary' in self._node.build:
            command.append('-o {}'.format(self._node.build.binary))
        else:
            command.append('-o {}'.format(self._te_name))

        if 'cwd' in self._node.build:
            command.insert(0, "cd {} &&".format(self._node.build.cwd, command))
        
        return " ".join(command)

    def __build_from_makefile(self):
        command = ["make"]
        
        return command


    def __construct_compil_tests(self, buildname):
        deps = []
        build_node = self._node.build

        if 'make' in build_node:
            command = self.__build_from_makefile()
        else:
            command = self.__build_from_sources()
            
        try:
            for d in build_node['depends_on']:
                deps.append(d if '.' in d else ".".join([self._te_pkg, d]))
        except KeyError as e:
            pass

        yield Test(
            name=buildname,
            command=command,
            constraint="compilation",
            dep=deps,
            time=self._node.validate.time.get("mean_time", None),
            delta=self._node.validate.time.get("tolerance", None),
            rc=self._node.validate.get("expect_exit", 0),
            resources=1,
            extras=None,
            postscript=None
        )
    
    def __construct_runtime_tests(self, buildname=None):
        #TODO: handle runtime filters (dynamic import)
        for comb in helper.gen_combinations(self._criterion):
            command = helper.prepare_run_command(comb)
            deps = [buildname] if buildname is not None else [None]
            try:
                for d in self._node.run.get('depends_on', []):
                    deps.append(d if '.' in d else ".".join([self._te_pkg, d]))
            except KeyError as e:
                pass
            yield Test(
                name="_".join([self._full_name, helper.stringify_combination(comb)]),
                command=command,
                dep=deps,
                time=self._node.validate.time.get("mean_time", None),
                delta=self._node.validate.time.get("tolerance", None),
                rc=self._node.validate.get("expect_exit", 0),
                resources=comb[self._base_it] if self._base_it in comb else 1,
                extras=None,
                postscript=self._node.validate.script.get('path', None),
                build=None
            )


    def construct_tests(self):
        string = ""
        buildname = None

        if 'build' in self._node:
            buildname = "_".join([self._full_name, "build"])
            yield from self.__construct_compil_tests(buildname)

        if 'run' in self._node:
            yield from self.__construct_runtime_tests(buildname)
    
 
    @property
    def tests(self):
        return self._tests


    def crit_override(self):
        return self._override

    def __repr__(self):
        return repr(self._node)
