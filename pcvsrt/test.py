import os

import yaml
from addict import Dict

from pcvsrt.helpers import io, log, lowtest
from pcvsrt.helpers.system import sysTable


class Test:
    def __init__(self, **kwargs):
        self._array = kwargs
    
    def serialize(self):
        string = "<job>"
        string += "{}".format(lowtest.xml_setif(self._array, 'name'))
        string += "{}".format(lowtest.xml_setif(self._array, 'command'))
        string += "<deps>{}</deps>".format(lowtest.xml_setif(self._array, 'dep'))
        string += "{}".format(lowtest.xml_setif(self._array, "rc"))
        string += "{}".format(lowtest.xml_setif(self._array, 'time'))
        string += "{}".format(lowtest.xml_setif(self._array, 'delta'))
        string += "{}".format(lowtest.xml_setif(self._array, 'resources'))
        string += "{}".format(lowtest.xml_setif(self._array, 'extras'))
        string += "{}".format(lowtest.xml_setif(self._array, 'postscript'))
        string += "<constraints>{}</constraints>".format(lowtest.xml_setif(self._array, 'constraint'))
        string += "</job>"
        return string


class TEDescriptor(yaml.YAMLObject):
    @classmethod
    def init_system_wide(cls, crit, base_it):
        cls._sys_crit = Dict(crit)
        cls._base_it = base_it

    
    def __init__(self, name, node, label, subprefix):
        if not isinstance(node, dict):
            log.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._te_name = name
        self._te_pkg = ".".join([label, subprefix.replace('/', '.')])
        _, self._srcdir, _, self._buildir = io.generate_local_variables(label, subprefix)
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
                    values = lowtest.unfold_sequence(v_sys['values'], self._sys_crit[k_sys]['values'])
                    if not values:
                        log.warn("No valid intersection found for '{}, Discard".format(k_sys))
                    else:
                        tmp[k_sys] = values
                else:  # key is not overriden
                    tmp[k_sys] = v_sys

            # now build program iterators
            if 'program' in it_node.iterate:
                self._criterion_user = it_node.iterate.program.keys()
                tmp.update(it_node.iterate.program)
            self._criterion = tmp

    def __build_from_sources(self):
        command = list()
        build_node = self._node.build
        lang = lowtest.detect_source_lang(build_node.files)
        command.append(sysTable.compiler.commands.get(lang, 'echo'))
        command.append(lowtest.prepare_cmd_build_variants(build_node.variants))
        command.append('{}'.format(build_node.get('cflags', '')))
        command.append('{}'.format(" ".join([build_node.files])))
        command.append('{}'.format(build_node.get('ldflags', '')))

        binary = self._node.build.sources.binary if 'binary' in self._node.build.sources else self._te_name
        command.append('-o {}'.format(os.path.join(self._buildir, binary)))

        if 'cwd' in self._node.build:
            command.insert(0, "cd {} &&".format(self._node.build.cwd))
        
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
        command.append('PCVS_CC="{}"'.format(sysTable.compiler.commands.get('cc', '')))
        command.append('PCVS_CXX="{}"'.format(sysTable.compiler.commands.get('cxx', '')))
        command.append('PCVS_CU="{}"'.format(sysTable.compiler.commands.get('cu', '')))
        command.append('PCVS_FC="{}"'.format(sysTable.compiler.commands.get('fc', '')))
        command.append('PCVS_CFLAGS="{} {}"'.format(
            lowtest.prepare_cmd_build_variants(build_node.variants),
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
        except KeyError:
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

        for comb in lowtest.gen_combinations(self._criterion):
            # TODO: filter according to runtime capabilities
            deps = [self._full_name] if 'build' in self._node else []
            try:
                for d in self._node.run.get('depends_on', []):
                    deps.append(d if '.' in d else ".".join([self._te_pkg, d]))
            except KeyError:
                pass

            command = lowtest.prepare_run_command(
                comb,
                {k: v for k, v in self._criterion.items() if k in self._criterion_user},
                os.path.join(self._buildir, self._node.run.get('program', 'a.out'))
            )

            yield Test(
                name="_".join([self._full_name, lowtest.stringify_combination(comb)]),
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
        if 'build' in self._node:
            yield from self.__construct_compil_tests()

        if 'run' in self._node:
            yield from self.__construct_runtime_tests()

    def __repr__(self):
        return repr(self._node)
