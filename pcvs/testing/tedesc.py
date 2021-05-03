import copy
import os
import re
from xml.sax.saxutils import escape

from addict import Dict

from pcvs import PATH_INSTDIR
from pcvs.helpers import log, pm, utils
from pcvs.helpers.criterion import Criterion, Serie
from pcvs.helpers.exceptions import TestException
from pcvs.helpers.system import MetaConfig
from pcvs.testing.test import Test


# ######################################
# ##### TEST: INPUT TRANSFORMATION #####
# ######################################
def detect_source_lang(array_of_files):
    detect = list()
    for f in array_of_files:
        if re.search(r'\.(h|H|i|I|s|S|c|c90|c99|c11)$', f):
            detect.append('cc')
        elif re.search(r'\.C|cc|cxx|cpp|c\+\+$', f):
            detect.append('cxx')
        elif re.search(r'\.(f|F)(77)$', f):
            detect.append('f77')
        elif re.search(r'\.(f|F)90$', f):
            detect.append('f90')
        elif re.search(r'\.(f|F)95$', f):
            detect.append('f95')
        elif re.search(r'\.(f|F)(20)*03$', f):
            detect.append('f03')
        elif re.search(r'\.(f|F)(20)*08$', f):
            detect.append('f08')
        elif re.search(r'\.(f|F)$', f):
            detect.append('fc')

    # now return the first valid language, according to settings
    # order matters: if sources contains multiple languages, the first
    # appearing in this list will be considered as the main language
    for i in ['f08', 'f03', 'f95', 'f90', 'f77', 'fc', 'cxx', 'cc']:
        if i in detect and i in MetaConfig.root.compiler.commands:
            return i
    return 'cc'


def prepare_cmd_build_variants(variants=[], comb=None):
    s = ""
    variant_def = MetaConfig.root.compiler.variants
    for i in variants:
        
        print(variants, variant_def)
        if i in variant_def.keys():
            s = "{} {}".format(s, variant_def[i].args)
    return s


def handle_job_deps(deps_node, pkg_label, pkg_prefix):
    deps = list()
    if 'depends_on' in deps_node:
        for name, values in deps_node['depends_on'].items():
            if name == 'test':
                for d in values:
                    deps.append(d if '/' in d else "/".join(filter(None, [pkg_label, pkg_prefix, d])))
            else:
                deps += [d for d in pm.identify({name: values})]
    return deps


def xml_escape(s):
    return escape(s, entities={
        "'": "&apos;",
        "\"": "&quot;"
    })


def xml_setif(elt, k, tag=None):
    if tag is None:
        tag = k
    if k in elt.keys() and elt[k] is not None:
        if isinstance(elt[k], list):
            return "".join(["<"+tag+">"+xml_escape(str(i))+"</"+tag+">" for i in elt[k]])
        else:
            return "<"+tag+">"+xml_escape(str(elt[k]))+"</"+tag+">"
    else:
        return ""


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
        self._te_label = label
        self._te_subtree = subprefix
        
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
        self._artifacts = Dict(node.get('artifact', None))
        self._template = node.get('group', None)
        self._debug = self._te_name+":\n"
        self._effective_cnt = 0
        self._full_name = "/".join(filter(None, [self._te_label, self._te_subtree, self._te_name]))
        self._tags = node.get('tag', list())
        
        for elt_k, elt_v in self._artifacts.items():
            if not os.path.isabs(elt_v):
                self._artifacts[elt_k] = os.path.join(self._buildir, elt_v)


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
        lang = detect_source_lang(self._build.files)
        binary = self._te_name
        if self._build.sources.binary:
            binary = self._build.sources.binary
        elif self._run.program:
            binary = self._run.program
        self._build.sources.binary = binary
        
        for i in range(0, len(self._build.files)):
            if not os.path.isabs(self._build.files[i]):
                self._build.files[i] = os.path.join(self._srcdir, self._build.files[i])
                

        command = "{cc} {var} {cflags} {files} {ldflags} {out}".format(
            cc=MetaConfig.root.compiler.commands.get(lang, 'echo'),
            var=prepare_cmd_build_variants(self._build.variants),
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
                var=prepare_cmd_build_variants(self._build.variants),
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
                var=prepare_cmd_build_variants(self._build.variants),
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
                var=prepare_cmd_build_variants(self._build.variants),
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
        else:
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
        deps = handle_job_deps(self._build, self._te_label, self._te_subtree)

        if 'cwd' in self._build:
            chdir = self._build.cwd

        tags = ["compilation"] + self._tags
        
        command = self.__build_command()

        # count number of built tests
        self._effective_cnt += 1
        yield Test(
            te_name=self._te_name,
            label=self._te_label,
            subtree=self._te_subtree,
            name=self._full_name,
            command=command,
            tags=tags,
            dep=deps,
            nb_res=1,
            time=self._validation.time.get("mean", None),
            delta=self._validation.time.get("tolerance", 0),
            rc=self._validation.get("expect_exit", 0),
            artifacts=self._artifacts,
            resources=1,
            comb_dict=None,
            valscript=None,
            env=None,
            matchers=None,
            chdir=chdir
        )
    
    def __construct_runtime_tests(self):
        """function steering tests to be run by the runtime command"""
        te_deps = handle_job_deps(self._run, self._te_label, self._te_subtree)
        
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
                label=self._te_label,
                subtree=self._te_subtree,
                name="_".join([self._full_name, comb.translate_to_str()]),
                command=command,
                dep=deps,
                tags=self._tags,
                env=env,
                nb_res=1,
                time=self._validation.time.get("mean", None),
                delta=self._validation.time.get("tolerance", 0),
                rc=self._validation.get("expect_exit", 0),
                resources=comb.get(self._base_it, 1),
                valscript=self._validation.script.get('path', None),
                build=None,
                comb_dict=comb.translate_to_dict(),
                chdir=chdir,
                artifacts=self._artifacts,
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
