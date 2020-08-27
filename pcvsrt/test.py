import os

import yaml
from addict import Dict

from pcvsrt.helpers import io, log, lowtest
from pcvsrt.criterion import Criterion, Combinations
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

    @staticmethod
    def finalize_file(path, package, content):
        fn = os.path.join(path, "list_of_tests.xml")
        with open(fn, 'w') as fh:
            fh.write("<jobSuite>")
            fh.write(content)
            fh.write("</jobSuite>")
        return fn


class TEDescriptor:
    @classmethod
    def init_system_wide(cls, base_criterion_name):
        cls._sys_crit = sysTable.criterion.iterators
        cls._base_it = base_criterion_name

    
    def __init__(self, name, node, label, subprefix):
        if not isinstance(node, dict):
            log.err(
                "Unable to build a TestDescription "
                "from the given node (got {})".format(type(node)), abort=1)
        self._te_name = name
        self._te_label = node.get('label', self._te_name)
        self._te_pkg = ".".join([label, subprefix.replace('/', '.')]) if subprefix else label
        
        _, self._srcdir, _, self._buildir = io.generate_local_variables(label, subprefix)
        self._build = Dict(node.get('build', None))
        self._run = Dict(node.get('run', None))

        if 'program' in self._run.get('iterate', {}):
            self._program_criterion = {k: Criterion(k, v, True) for k, v in self._run.iterate.program.items()}
        else:
            self._program_criterion = None

        self._validation = Dict(node.get('validate', None))
        self._artifacts = Dict(node.get('artifacts', None))
        self._template = node.get('group', None)

        self._full_name = ".".join([self._te_pkg, self._te_name])
        
        self._configure_criterions()
        self._compatibility_support(node.get('_compat', None))

    def _compatibility_support(self, compat):
        if compat is None:
            return
        for k in compat:
            if 'chdir' in k:
                if self._build and 'cwd' not in self._build:
                    self._build.cwd = compat[k]
                if self._run and 'cwd' not in self._run:
                    self._run.cwd = compat[k]
            
            if 'type' in k:
                if compat[k] in ['build', 'complete']:
                    self._build.dummy = True
                if compat[k] in ['run', 'complete']:
                    self._run.dummy = True

            elif 'bin' in k:
                if self._build and 'binary' not in self._build:
                    self._build.binary = compat[k]
                if self._run and 'program' not in self._run:
                    self._run.program = compat[k]

    def _configure_criterions(self):
        if 'iterate' not in self._run:
            self._criterion = self._sys_crit
        else:
            te_keys = self._run.iterate.keys()
            tmp = {}
            for k_sys, v_sys in self._sys_crit.items():
                # if key is overriden by the test
                if k_sys in te_keys:
                    cur_criterion = Criterion(k_sys, self._run.iterate[k_sys])
                    cur_criterion.expand_values()
                    cur_criterion.intersect(v_sys)
                    if cur_criterion.is_empty():
                        log.warn("No valid intersection found for '{}, Discard".format(k_sys))
                    else:
                        tmp[k_sys] = cur_criterion
                else:  # key is not overriden
                    tmp[k_sys] = v_sys

            self._criterion = tmp
            # now build program iterators
            [elt.expand_values() for elt in self._program_criterion.values()]  

    def __build_from_sources(self):
        command = list()
        lang = lowtest.detect_source_lang(self._build.files)
        command.append(sysTable.compiler.commands.get(lang, 'echo'))
        command.append(lowtest.prepare_cmd_build_variants(self._build.variants))
        command.append('{}'.format(self._build.get('cflags', '')))
        command.append('{}'.format(" ".join(self._build.files)))
        command.append('{}'.format(self._build.get('ldflags', '')))

        binary = self._build.sources.binary if 'binary' in self._build.sources else self._te_name
        command.append('-o {}'.format(os.path.join(self._buildir, binary)))

        if 'cwd' in self._build:
            command.insert(0, "cd {} &&".format(self._build.cwd))
        
        return " ".join(command)

    def __build_from_makefile(self):
        command = ["make"]
        if 'files' in self._build:
            basepath = os.path.dirname(self._build.files[0])
            command.append("-f {}".format(" ".join(self._build.files)))
        else:
            basepath = self._srcdir
        
        command.append("-C {}".format(basepath))
        command.append("{}".format(self._build.make.get('target', '')))
        command.append('PCVS_CC="{}"'.format(sysTable.compiler.commands.get('cc', '')))
        command.append('PCVS_CXX="{}"'.format(sysTable.compiler.commands.get('cxx', '')))
        command.append('PCVS_CU="{}"'.format(sysTable.compiler.commands.get('cu', '')))
        command.append('PCVS_FC="{}"'.format(sysTable.compiler.commands.get('fc', '')))
        command.append('PCVS_CFLAGS="{} {}"'.format(
            lowtest.prepare_cmd_build_variants(self._build.variants),
            self._build.get('cflags', '')
        ))
        command.append('PCVS_LDFLAGS="{}"'.format(self._build.get('ldflags', '')))
        return " ".join(command)

    def __construct_compil_tests(self):
        deps = []
        
        if not isinstance(self._build.files, list):
            self._build.files = list(self._build.files)

        if 'make' in self._build:
            command = self.__build_from_makefile()
        else:
            command = self.__build_from_sources()
            
        try:
            for d in self._build['depends_on']:
                deps.append(d if '.' in d else ".".join([self._te_pkg, d]))
        except KeyError:
            pass

        yield Test(
            name=self._full_name,
            command=command,
            constraint="compilation",
            dep=deps,
            time=self._validation.time.get("mean_time", None),
            delta=self._validation.time.get("tolerance", None),
            rc=self._validation.get("expect_exit", 0),
            resources=1,
            extras=None,
            postscript=None
        )
    
    def __construct_runtime_tests(self):
        #TODO: handle runtime filters (dynamic import)

        for comb in Combinations({**self._criterion, **self._program_criterion}).generate():
            # TODO: filter according to runtime capabilities
            deps = [self._full_name] if self._build else []
            for d in self._run.get('depends_on', []):
                deps.append(d if '.' in d else ".".join([self._te_pkg, d]))

            envs, args, params = comb.translate_to_command()

            command = [
                " ".join(envs),
                sysTable.runtime.program,
                " ".join(args),
                os.path.join(self._buildir, self._run.get('program', self._build.get('binary', 'a.out'))),
                " ".join(params)
            ]

            yield Test(
                name="_".join([self._full_name, comb.translate_to_str()]),
                command=" ".join(command),
                dep=deps,
                time=self._validation.time.get("mean_time", None),
                delta=self._validation.time.get("tolerance", None),
                rc=self._validation.get("expect_exit", 0),
                resources=comb.get(self._base_it, 1),
                extras=None,
                postscript=self._validation.script.get('path', None),
                build=None
            )

    def construct_tests(self):
        if self._build:
            yield from self.__construct_compil_tests()

        if self._run:
            yield from self.__construct_runtime_tests()

    def __repr__(self):
        return repr(self._build) + repr(self._run) + repr(self._validation)
