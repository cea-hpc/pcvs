from pcvsrt import logs, helper, context
from pcvsrt.context import settings
import yaml
import os
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
    return set(x) | sys
                    


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

    
    def __init__(self, name, node, label, subprefix):
        if not isinstance(node, dict):
            logs.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._te_name = name
        self._te_pkg = ".".join([label, subprefix.replace('/', '.')])
        _, self._srcdir, _, self._buildir = helper.generate_local_variables(label, subprefix)
        self._node = Dict(node)
        self._full_name = ".".join([self._te_pkg, self._te_name])
        self._criterion = Dict()

        self._refine_iterators()
        self._compatibility_support()

    def _compatibility_support(self):
        if '_compat' not in self._node:
            return
        for k in self._node._compat:
            if 'chdir' in k:
                if 'build' in self._node and 'cwd' not in self._node.build:
                    self._node.build.cwd = self._node._compat[k]
                if 'run' in self._node and 'cwd' not in self._node.run:
                    self._node.run.cwd = self._node._compat[k]
            
            if 'type' in k:
                if self._node._compat[k] in ['build', 'complete']:
                    self._node.build.dummy = True
                if self._node._compat[k] in ['run', 'complete']:
                    self._node.run.dummy = True

            elif 'bin' in k:
                print('build' in self._node)
                if 'build' in self._node and 'binary' not in self._node.build:
                    self._node.build.binary = self._node._compat[k]
                if 'run' in self._node and 'program' not in self._node.run:
                    self._node.run.program = self._node._compat[k]
                
        self._node.pop("_compat")

    def _refine_iterators(self):
        it_node = self._node.run
        if 'iterate' not in it_node:
            self._criterion = self._sys_crit
        else:
            te_keys = self._node.iterate.keys()
            tmp = {}
            for k_sys, v_sys in self._sys_crit.items():
                # if key is overriden by the test
                if k_sys in te_keys:
                    values = unfold_sequence(v_sys['values'], self._sys_crit[k_sys]['values'])
                    if not values:
                        logs.warn("No valid intersection found for '{}, Discard".format(k_sys))
                    else:
                        tmp[k_sys] = values
                else:  # key is not overriden
                    tmp[k_sys] = v_sys

            # now build program iterators
            if 'program' in it_node.iterate:
                self._criterion_user = it_node.iterate.program.keys()
                tmp.update(it_node.iterate.program)
            self._criterion = tmp

    @property
    def name(self):
        return self._name

    def has_build_rule(self):
        return self._node['build']

    def __build_from_sources(self):
        command = list()
        build_node = self._node.build
        lang = helper.detect_source_lang(build_node.files)
        command.append(settings.compiler.commands.get(lang, 'echo'))
        command.append(helper.prepare_cmd_build_variants(build_node.variants))
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
        build_node = self._node.build
        command = ["make"]
        if 'files' in build_node:
            basepath = os.path.dirname(build_node.files)
            command.append("-f {}".format(" ".join([build_node.files])))
        else:
            basepath = self._srcdir
        
        command.append("-C {}".format(basepath))
        command.append("{}".format(build_node.make.get('target', '')))
        command.append('PCVS_CC="{}"'.format(settings.compiler.commands.get('cc', '')))
        command.append('PCVS_CXX="{}"'.format(settings.compiler.commands.get('cxx', '')))
        command.append('PCVS_CU="{}"'.format(settings.compiler.commands.get('cu', '')))
        command.append('PCVS_FC="{}"'.format(settings.compiler.commands.get('fc', '')))
        command.append('PCVS_CFLAGS="{} {}"'.format(
            helper.prepare_cmd_build_variants(build_node.variants),
            build_node.get('cflags', '')
        ))
        command.append('PCVS_LDFLAGS="{}"'.format(build_node.get('ldflags', '')))
            
        return " ".join(command)


    def __construct_compil_tests(self):
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
            name=self._full_name,
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
    
    def __construct_runtime_tests(self):
        #TODO: handle runtime filters (dynamic import)

        for comb in helper.gen_combinations(self._criterion):
            # TODO: filter according to runtime capabilities
            deps = [self._full_name] if 'build' in self._node else []
            try:
                for d in self._node.run.get('depends_on', []):
                    deps.append(d if '.' in d else ".".join([self._te_pkg, d]))
            except KeyError as e:
                pass

            command = helper.prepare_run_command(
                comb,
                {k: v for k, v in self._criterion.items() if k in self._criterion_user},
                os.path.join(self._buildir, self._node.run.get('program', 'a.out'))
            )

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

        if 'build' in self._node:
            yield from self.__construct_compil_tests()

        if 'run' in self._node:
            yield from self.__construct_runtime_tests()
    
 
    @property
    def tests(self):
        return self._tests

    def __repr__(self):
        return repr(self._node)
