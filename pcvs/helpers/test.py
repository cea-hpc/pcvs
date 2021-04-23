import copy
import functools
import operator
import os
import pathlib
import pprint
import subprocess

import jsonschema
import yaml
from addict import Dict

from pcvs import PATH_INSTDIR
from pcvs.helpers import log, system, test_transform, utils
from pcvs.helpers.criterion import Criterion, Serie
from pcvs.helpers.exceptions import TestException
from pcvs.helpers.package_manager import PManager
from pcvs.helpers.system import MetaConfig


class TestFileError(Exception):
    def __init__(self):
        pass


def __load_yaml_file_legacy(f):
    """Legacy version to load a YAML file.

    This function intends to be backward-compatible with old YAML syntax
    by relying on external converter (not perfect).
    """
    # Special case: old files required non-existing tags to be resolved
    old_group_file = os.path.join(PATH_INSTDIR, "templates/group-compat.yml")

    proc = subprocess.Popen(
        "pcvs_convert '{}' --stdout -k te -t '{}'".format(
                f,
                old_group_file
            ).split(),
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        shell=True)

    fds = proc.communicate()
    if proc.returncode != 0:
        raise TestFileError()

    return fds[0].decode('utf-8')


def replace_special_token(stream, src, build, prefix):
    tokens = {
        '@BUILDPATH@': os.path.join(build, prefix),
        '@SRCPATH@': os.path.join(src, prefix),
        '@ROOTPATH@': src,
        '@BROOTPATH@': build,
        '@SPACKPATH@': "TBD",
        '@HOME@': str(pathlib.Path.home()),
        '@USER@': os.environ['USER']
    }
    for k, v in tokens.items():
        stream = stream.replace(k, v)
    return stream


def load_yaml_file(f, source, build, prefix):
    """Load a YAML test description file."""
    need_conversion = False
    obj = {}
    try:
        with open(f, 'r') as fh:
            stream = fh.read()
            stream = replace_special_token(stream, source, build, prefix)
            obj = yaml.safe_load(stream)
    # badly formatted YAML
    except yaml.YAMLError:
        need_conversion = True
    
    # attempt to convert of the fly the YAML file
    if need_conversion:
        log.manager.debug("\t--> Legacy syntax: {}".format(f))
        obj = yaml.safe_load(__load_yaml_file_legacy(f))

        # when 'debug' is activated, print the converted YAML file
        if log.manager.has_verb_level('debug'):
            cv_file = os.path.join(os.path.split(f)[0], "converted-pcvs.yml")
            log.manager.debug("\t--> Stored file to {}".format(cv_file))
            with open(cv_file, 'w') as fh:
                yaml.safe_dump(obj, fh)
    return obj


class TestFile:
    cc_pm_string = ""
    rt_pm_string = ""
    val_scheme = None

    def __init__(self, file_in, path_out, data=None, label=None, prefix=None):
        self._in = file_in
        self._path_out = path_out
        self._raw = data
        self._label = label
        self._prefix = prefix
        self._tests = list()
        self._debug = dict()
        if TestFile.val_scheme is None:
            TestFile.val_scheme = system.ValidationScheme('te')
        
    def process(self, check=True):
        """Load the YAML file and map YAML nodes to Test()"""
        src, _, build, _ = utils.generate_local_variables(
            self._label,
            self._prefix)
        
        if self._raw is None:
            self._raw = load_yaml_file(self._in, src, build, self._prefix)
        # optionally validate user's input
        # this check should also be used while loading the file.
        # (old syntax files will only be converted if they are wrongly
        # formatted, not if they are invalid)
        if check is True:
            try:
                TestFile.val_scheme.validate(self._raw, filepath=self._in)
            except jsonschema.ValidationError as e:
                self._debug['.yaml_errors'].append(e)

        # main loop, parse each node to register tests
        for k, content, in self._raw.items():
            td = TEDescriptor(k, content, self._label, self._prefix)
            for test in td.construct_tests():
                self._tests.append(test)
            
            # register debug informations relative to the loaded TEs
            self._debug[k] = td.get_debug()
    
    def flush_sh_file(self):
        """Store the given input file into their destination.
        This function dumps the Shell file, used as JCHRONOSS test command
        manager"""
        fn_sh = os.path.join(self._path_out, "list_of_tests.sh")
        cobj = MetaConfig.root.get_internal('cc_pm')
        if TestFile.cc_pm_string == "" and cobj:
            TestFile.cc_pm_string = "\n".join([
                    e.get(load=True, install=False)
                    for e in cobj
                ])
        
        robj = MetaConfig.root.get_internal('rt_pm')
        if TestFile.rt_pm_string == "" and robj:
            TestFile.rt_pm_string = "\n".join([
                    e.get(load=True, install=False)
                    for e in robj
                ])

        with open(fn_sh, 'w') as fh_sh:
            fh_sh.write(
                '#!/bin/sh\n' +
                '{pm_string}\n'.format(pm_string="\n".join([
                        TestFile.cc_pm_string,
                        TestFile.rt_pm_string
                    ])) +
                'for arg in "$@"; do\n' +
                '   case $arg in\n')

            for test in self._tests:
                fh_sh.write(test.generate_script())
                MetaConfig.root.get_internal('orchestrator').add_new_job(test)

            fh_sh.write(
                '   --list)\n'
                '       printf "{list_of_tests}\\n"\n'
                '       ;;\n'
                '   *)\n'
                '       printf "Invalid test-name \'$arg\'\\n"\n'
                '       exit 1\n'
                '   esac\n'
                'done\n'
                'exit $ret\n'.format(list_of_tests="\n".join([
                            t.name
                            for t in self._tests
                        ])))
        
        self.generate_debug_info()

    def generate_debug_info(self):
        """Dump debug info to the appropriate file for the input object"""
        if len(self._debug) and log.manager.has_verb_level('info'):
            with open(os.path.join(self._path_out, "dbg-pcvs.yml"), 'w') as fh:
                # compute max number of combinations from system iterators
                sys_cnt = functools.reduce(
                    operator.mul,
                    [
                        len(v['values'])
                        for v in MetaConfig.root.criterion.iterators.values()
                    ]
                )
                self._debug.setdefault('.system-values', {})
                self._debug['.system-values'].setdefault('stats', {})

                for c_k, c_v in MetaConfig.root.criterion.iterators.items():
                    self._debug[".system-values"][c_k] = c_v['values']
                self._debug[".system-values"]['stats']['theoric'] = sys_cnt
                yaml.safe_dump(self._debug, fh, default_flow_style=None)


class Test:
    STATE_OTHER = -1
    STATE_NOT_EXECUTED = 0
    STATE_SUCCEED = 1
    STATE_FAILED = 2
    STATE_INVALID_SPEC = 3

    _strstate = {
        STATE_OTHER: 'OTHER',
        STATE_NOT_EXECUTED: 'NOT_EXEC',
        STATE_SUCCEED: 'SUCCESS',
        STATE_FAILED: 'FAILURE',
        STATE_INVALID_SPEC: 'INVALID'
    }

    """A basic test representation, from one step to concretize the logic
    to the JCHRONOSS input datastruct."""
    def __init__(self, **kwargs):
        """register a new test"""
        self._array = kwargs
        self._executed = False
        self._rc = 0
        self._time = 0.0
        self._out = None
        self._state = self.STATE_NOT_EXECUTED
    
    def override_cmd(self, cmd):
        self._array['command'] = cmd
    
    @property
    def name(self):
        return self._array['name']

    @property
    def command(self):
        return self._array['command']
        
    def get_dim(self, unit="n_node"):
        return self._array['nb_res']

    def save_final_result(self, rc=0, time=0.0, out=None):
        self._rc = rc
        self._out = out
        self._time = time

    def executed(self):
        if self._state == self.STATE_NOT_EXECUTED:
            self._state = self.STATE_OTHER

        self._executed = True

    def been_executed(self):
        return self._executed
    
    @property
    def state(self):
        return self._state
    
    @property
    def strstate(self):
        return self._strstate[self._state]

    def to_json(self):
        return {
            "id" : {
                "te_name": self._array["te_name"],
                "label" : "TBD",
                "subtree" : self._array["subtree"],
                "full_name": self._array["name"]
            },
            "exec": self._array["command"],
            "result": {
                "state": self._state if self._executed else self.STATE_NOT_EXECUTED,
                "time": self._time,
                "output": self._out,
            },
            "data": {
                "tags": "TBD",
                "metrics": "TBD",
                "artifacts": "TBD",
                "comb": "TBD"
            }
        }
    

    def generate_script(self):
        """Serialize test logic to its Shell representation"""
        pm_code = ""
        cd_code = ""
        env_code = ""
        final_code = ""

        # if changing directory is required by the test
        if self._array['chdir'] is not None:
            cd_code += "cd '{}'\n".format(self._array['chdir'])

        # manage package-manager deps
        if self._array['dep'] is not None:
            pm_code += "\n".join([
                    elt.get(load=True, install=True)
                    for elt in self._array['dep']
                    if isinstance(elt, PManager)
                ])
        
        # manage environment variables defined in TE
        if self._array['env'] is not None:
            for e in self._array['env']:
                env_code += "{}; export {}\n".format(e, e.split('=')[0])

        # if test should be validated through a matching regex
        if self._array['matchers'] is not None:
            for k, v in self._array['matchers'].items():
                expr = v['expr']
                required = (v.get('expect', True) is True)
                # if match is required set 'ret' to 1 when grep fails
                final_code += "{echo} | {grep} '{expr}' {fail} ret=1\n".format(
                    echo='echo "$output"',
                    grep='grep -qP',
                    expr=expr,
                    fail='||' if required else "&&")
        
        # if a custom script is provided (in addition or not to matchers)
        if self._array['valscript'] is not None:
            final_code += "{echo} | {script}; ret=$?".format(
                echo='echo "$output"',
                script=self._array['valscript']
            )
        
        return """
        "{name}")
            case "$PCVS_SHOW" in
                env) echo "{env_code}"; exit 0;;
                cmd) echo "{cmd}"; exit 0;;
                loads) echo "{pm_esc}"; exit 0;;
            esac
            {cd_code}
            {pm_code}
            {env_code}
            output=`{cmd} 2>&1`
            ret=$?
            echo "$output"
            {finalize}
            ;;""".format(
                    cd_code=cd_code,
                    pm_code=pm_code,
                    pm_esc=pm_code.replace(r'$', r'\$').replace(r'`', r'\`'),
                    env_code=env_code,
                        name=self._array['name'],
                    cmd=self._array['command'],
                    finalize=final_code
                )


class TEDescriptor:
    """Maps to a program description, as read by YAML user files"""
    @classmethod
    def init_system_wide(cls, base_criterion_name):
        """Initialize system-wide information (to shorten accesses)"""
        cls._sys_crit = MetaConfig.root.get_internal('crit_obj')
        cls._base_it = base_criterion_name

    def __init__(self, name, node, label, subprefix):
        """load a new TEDescriptor from a given YAML node"""
        if not isinstance(node, dict):
            raise TestException.TDFormatError(node)
        self._te_name = name
        self._skipped = name.startswith('.')
        self._te_label = node.get('label', self._te_name)
        self._te_pkg = "/".join([label, subprefix]) if subprefix else label
        
        _, self._srcdir, _, self._buildir = utils.generate_local_variables(
                label,
                subprefix
            )
        # before doing anything w/ node:
        # arregate the 'group' definitions with the TE
        # to get all the fields in their final form
        if 'group' in node:
            assert(node['group'] in MetaConfig.root.group.keys())
            tmp = Dict(MetaConfig.root.group[node['group']])
            tmp.update(Dict(node))
            node = tmp
        # load from descriptions
        self._build = Dict(node.get('build', None))
        self._run = Dict(node.get('run', None))
        self._validation = Dict(node.get('validate', None))
        self._artifacts = Dict(node.get('artifacts', None))
        self._template = node.get('group', None)
        self._debug = self._te_name+":\n"
        self._effective_cnt = 0
        self._full_name = "/".join([self._te_pkg, self._te_name])
        self._tags = node.get('tag', list())

        # allow tags to be given as array OR a single string
        if not isinstance(self._tags, list):
            self._tags = [self._tags]
        
        # if TE used program-level criterions
        if 'program' in self._run.get('iterate', {}):
            self._program_criterion = {
                    k: Criterion(k, v, local=True)
                    for k, v in self._run.iterate.program.items()
                }
        else:
            self._program_criterion = {}

        # compute local criterions relatively to system-wide's
        self._configure_criterions()
        # apply retro-compatibility w/ old syntax
        self._compatibility_support(node.get('_compat', None))

    def _compatibility_support(self, compat):
        """Convert tricky keywords from old syntax too complex to be handled
        by the automatic converter."""
        if compat is None:
            return
        for k in compat:
            # the old 'chdir' may be used by run & build
            # but should not be set for one if the whole 
            # parent node does not exist
            if 'chdir' in k:
                if self._build and 'cwd' not in self._build:
                    self._build.cwd = compat[k]
                if self._run and 'cwd' not in self._run:
                    self._run.cwd = compat[k]
            
            # the old 'type' keyword disappeared. Still, the 'complete'
            # keyword must be handled to create both nodes 'build' & 'run'
            if 'type' in k:
                if compat[k] in ['build', 'complete']:
                    self._build.dummy = True
                if compat[k] in ['run', 'complete']:
                    self._run.dummy = True

            # same as for chdir, 'bin' may be used by both build & run
            # but should set either not existing already
            elif 'bin' in k:
                if self._build and 'binary' not in self._build:
                    self._build.binary = compat[k]
                if self._run and 'program' not in self._run:
                    self._run.program = compat[k]

    def _configure_criterions(self):
        """Prepare the list of components this TE will be built against"""
        if self._run is None:
            # for now, criterion only applies to run tests
            return

        # if this TE does not override anything: trivial
        if 'iterate' not in self._run:
            self._criterion = self._sys_crit
        else:
            te_keys = self._run.iterate.keys()
            tmp = {}
            # browse declared criterions (system-wide)
            for k_sys, v_sys in self._sys_crit.items():
                # if key is overriden by the test
                if k_sys in te_keys:
                    cur_criterion = copy.deepcopy(v_sys)
                    cur_criterion.override(self._run.iterate[k_sys])
                    
                    if cur_criterion.is_discarded():
                        continue
                    # merge manually some definitions made by
                    # runtime, as some may be required to expand values:
                    
                    cur_criterion.expand_values()
                    cur_criterion.intersect(v_sys)
                    if cur_criterion.is_empty():
                        self._skipped = True
                    else:
                        tmp[k_sys] = cur_criterion
                else:  # key is not overriden
                    tmp[k_sys] = v_sys

            self._criterion = tmp
            # now build program iterators
            for _, elt in self._program_criterion.items():
                elt.expand_values()

    def __build_from_sources(self):
        """Specific to build rule, where the compilation is made from a
        collection of source files"""
        lang = test_transform.detect_source_lang(self._build.files)
        binary = self._te_name

        if self._build.sources.binary:
            binary = self._build.sources.binary
        elif self._run.program:
            binary = self._run.program
        self._build.sources.binary = binary

        command = "{cc} {var} {cflags} {files} {ldflags} {out}".format(
            cc=MetaConfig.root.compiler.commands.get(lang, 'echo'),
            var=test_transform.prepare_cmd_build_variants(self._build.variants),
            cflags=self._build.get('cflags', ''),
            files=" ".join(self._build.files),
            ldflags=self._build.get('ldflags', ''),
            out="-o {}".format(os.path.join(self._buildir, binary))
        )
        return command

    def __build_from_makefile(self):
        """Specific to build rule, where the compilation is managed by 
        a makefile"""
        command = ["make"]
        basepath = self._srcdir

        # change makefile path if overriden by 'files'
        if 'files' in self._build:
            basepath = os.path.dirname(self._build.files[0])
            command.append("-f {}".format(" ".join(self._build.files)))
        
        # build the 'make' command
        command.append(
            '-C {path} {target} '
            'PCVS_CC="{cc}" PCVS_CXX="{cxx}" PCVS_CU="{cu}" PCVS_FC="{fc}" '
            'PCVS_CFLAGS="{var} {cflags}" PCVS_LDFLAGS="{ldflags}"'.format(
                path=basepath,
                target=self._build.make.get('target', ''),
                cc=MetaConfig.root.compiler.commands.get('cc', ''),
                cxx=MetaConfig.root.compiler.commands.get('cxx', ''),
                fc=MetaConfig.root.compiler.commands.get('fc', ''),
                cu=MetaConfig.root.compiler.commands.get('cu', ''),
                var=test_transform.prepare_cmd_build_variants(self._build.variants),
                cflags=self._build.get('cflags', ''),
                ldflags=self._build.get('ldflags', '')
            )
        )
        return " ".join(command)

    def __build_from_cmake(self):
        command = ["cmake"]
        if 'files' in self._build:
            command.append(self._build.files[0])
        else:
            command.append(self._srcdir)
        command.append(
            r"-DCMAKE_C_COMPILER='{cc}' -DCMAKE_CXX_COMPILER='{cxx}' "
            r"-DCMAKE_FC_COPILER='{fc}' -DCMAKE_CUDA_COMPILER='{cu}' "
            r"-DCMAKE_C_FLAGS='{var} {cflags}' -DCMAKE_EXE_LINKER_FLAGS='{ldflags}' "
            r"-G 'Unix Makefiles' "
            r"-DCMAKE_BINARY_DIR='{build}' "
            r"-DCMAKE_MODULE_LINKER_FLAGS='{ldflags}' "
            r"-DCMAKE_SHARED_LINKER_FLAGS='{ldflags}'".format(
                cc=MetaConfig.root.compiler.commands.get('cc', ''),
                cxx=MetaConfig.root.compiler.commands.get('cxx', ''),
                fc=MetaConfig.root.compiler.commands.get('fc', ''),
                cu=MetaConfig.root.compiler.commands.get('cu', ''),
                var=test_transform.prepare_cmd_build_variants(self._build.variants),
                cflags=self._build.get('cflags', ''),
                ldflags=self._build.get('ldflags', ''),
                build=self._buildir
            )
        )
        if 'vars' in self._build['cmake']:
            command.append("-D"+' -D'.join(self._build['cmake']['vars']))

        self._build.files = [os.path.join(self._buildir, "Makefile")]
        next_command = self.__build_from_makefile()
        return " && ".join([" ".join(command), next_command])

    def __build_from_autotools(self):
        command = []
        configure_path = ""
        autogen_path = ""

        if self._build.get('files', False):
            configure_path = self._build.files[0]
        else:
            configure_path = os.path.join(self._srcdir, "configure")
        
        if self._build.autotools.get('autogen', False) is True:
            autogen_path = os.path.join(
                                os.path.dirname(configure_path),
                                "autogen.sh"
                            )
            command.append("{} && ".format(autogen_path))
        
        command.append(
            r"{configure} "
            r"CC='{cc}' CXX='{cxx}' "
            r"FC='{fc}' NVCC='{cu}' "
            r"CFLAGS='{var} {cflags}' LDFLAGS='{ldflags}' ".format(
                configure=configure_path,
                cc=MetaConfig.root.compiler.commands.get('cc', ''),
                cxx=MetaConfig.root.compiler.commands.get('cxx', ''),
                fc=MetaConfig.root.compiler.commands.get('fc', ''),
                cu=MetaConfig.root.compiler.commands.get('cu', ''),
                var=test_transform.prepare_cmd_build_variants(self._build.variants),
                cflags=self._build.get('cflags', ''),
                ldflags=self._build.get('ldflags', ''),
            )
        )
        if 'params' in self._build['autotools']:
            command.append(" ".join(self._build['autotools']['params']))

        self._build.files = [os.path.join(self._buildir, "Makefile")]
        next_command = self.__build_from_makefile()
        return " && ".join([" ".join(command), next_command])
    
    def __build_command(self):
        if 'autotools' in self._build:
            return self.__build_from_autotools()
        elif 'cmake' in self._build:
            return self.__build_from_cmake()
        elif 'make' in self._build:
            return self.__build_from_makefile()
        elif 'sources' in self._build:
            return self.__build_from_sources()

    def __construct_compil_tests(self):
        """Meta-function steering compilation tests"""
        deps = []
        chdir = None
        
        # ensure consistency when 'files' node is used
        # can be a list or a single value
        if 'files' in self._build and not isinstance(self._build.files, list):
            self._build.files = [self._build.files]

        # manage deps (tests, package_managers...)
        deps = test_transform.handle_job_deps(self._build, self._te_pkg)

        if 'cwd' in self._build:
            chdir = self._build.cwd

        constraints = ["compilation"] + self._tags
        
        command = self.__build_command()

        # count number of built tests
        self._effective_cnt += 1

        yield Test(
            te_name=self._te_name,
            subtree=self._te_pkg,
            name=self._full_name,
            command=command,
            constraint=constraints,
            dep=deps,
            nb_res=1,
            time=self._validation.time.get("mean_time", None),
            delta=self._validation.time.get("tolerance", None),
            rc=self._validation.get("expect_exit", 0),
            resources=1,
            valscript=None,
            env=None,
            matchers=None,
            chdir=chdir
        )
    
    def __construct_runtime_tests(self):
        """function steering tests to be run by the runtime command"""
        te_deps = test_transform.handle_job_deps(self._run, self._te_pkg)
        
        # for each combination generated from the collection of criterions
        for comb in self._serie.generate():
            # clone deps as it may be updated by each test
            deps = copy.deepcopy(te_deps)
            chdir = None
            if self._build:
                deps.append(self._full_name)

            # start to build the proper command, three parts:
            # the environment variables to export
            # the runtime argument to propagate
            # the program parameters to forward
            env, args, params = comb.translate_to_command()
            
            # attempt to compute program/binary name
            program = self._te_name
            if self._run.program:
                program = self._run.program
            elif self._build.sources.binary:
                program = self._build.sources.binary
            
            # attempt to determine test working directory
            if self._run.cwd:
                chdir = self._run.cwd
                # if set, 'program' build is prefix w/ cwd path
                program = os.path.join(chdir, program)
            else:
                #else, prefix with @BUILDPATH@
                program = os.path.join(self._buildir, program)

            command = "{runtime} {runtime_args} {args} {program} {params}".format(
                runtime=MetaConfig.root.runtime.program,
                runtime_args=MetaConfig.root.runtime.get('args', ''),
                args=" ".join(args),
                program=program,
                params=" ".join(params)
            )

            self._effective_cnt += 1

            yield Test(
                te_name=self._te_name,
                subtree=self._te_pkg,
                name="_".join([self._full_name, comb.translate_to_str()]),
                command=command,
                dep=deps,
                constraint=self._tags,
                env=env,
                nb_res=1,
                time=self._validation.time.get("mean_time", None),
                delta=self._validation.time.get("tolerance", None),
                rc=self._validation.get("expect_exit", 0),
                resources=comb.get(self._base_it, 1),
                valscript=self._validation.script.get('path', None),
                build=None,
                chdir=chdir,
                matchers=self._validation.get('match', None)
            )

    def construct_tests(self):
        """Meta function to trigger test construction"""
        # if this TE does not lead to a single test, skip now
        if self._skipped:
            return

        if self._build:
            yield from self.__construct_compil_tests()
        if self._run:
            self._serie = Serie({**self._criterion, **self._program_criterion})
            yield from self.__construct_runtime_tests()

    def get_debug(self):
        """Build information debug for the current TE"""
        # if the current TE did not lead to a single test, skip now
        if self._skipped:
            return {}
        
        user_cnt = 1
        real_cnt = 1
        self._debug_yaml = dict()

        # count the compilation run
        if self._build:
            real_cnt = 1

        # count actual tests built
        if self._run:
            #for system-wide iterators, count max number of possibilites
            for k, v in self._criterion.items():
                self._debug_yaml[k] = list(v.values)
                real_cnt *= len(v.values)
            
            # for program-lavel iterators, count number of possibilies
            self._debug_yaml['program'] = dict()
            for k, v in self._program_criterion.items():   
                self._debug_yaml['program'][k] = list(v.values)
                user_cnt *= len(v.values)
        
        #store debug info
        self._debug_yaml['.stats'] = {
            'theoric': user_cnt * real_cnt,
            'program_factor': user_cnt,
            'effective': self._effective_cnt
            }

        return self._debug_yaml
    
    @property
    def name(self):
        return self._te_name

    def __repr__(self):
        """internal representation, for auto-dumping"""
        return repr(self._build) + repr(self._run) + repr(self._validation)
