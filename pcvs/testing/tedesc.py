import shutil
import tempfile
import copy
import os
import re

import pcvs
from pcvs import testing
from pcvs.helpers import pm
from pcvs.helpers.criterion import Criterion, Serie
from pcvs.helpers.exceptions import TestException, ProfileException
from pcvs.helpers.system import MetaConfig, MetaDict
from pcvs.testing.test import Test


def detect_source_lang(array_of_files):
    """Determine compilation language for a target file (or list of files).

    Only one language is detected at once.

    :param array_of_files: list of files to identify
    :type array_of_files: list
    :return: the language code
    :rtype: str
    """
    detect = list()
    for f in array_of_files:
        if re.search(r'\.(h|H|i|I|s|S|c|c90|c99|c11)$', f):
            detect.append('cc')
        elif re.search(r'\.(C|cc|cxx|cpp|c\+\+)$', f):
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
        if i in detect and i in MetaConfig.root.compiler:
            return i
    return 'cc'


def extract_compiler_config(lang, variants):
    """
    Build resource to compile based on language and variants involved.

    :param lang: target language
    :type lang: str
    :param variants: list of enabled variants
    :type variants: list
    :return: the program, its args and env modifiers (in that order)
    :rtype: tuple
    """
    if not lang or lang not in MetaConfig.root.compiler:
        raise ProfileException.IncompleteError(
            reason="Unknown language, not defined into Profile",
            dbg_info={"lang": lang, "list": MetaConfig.root.compiler.keys()}
        )
    
    config = MetaConfig.root.compiler[lang]
    for v in variants:
        if v in config.variants:
            for k, v in config.variants[v].items():
                if k == 'program':
                    config[k] = v
                else:
                    config.setdefault(k, list())
                    config[k] += v
        else:
            return (None, [], [])
                    
    return (config.program, config.args, config.envs)


def build_job_deps(deps_node, pkg_label, pkg_prefix):
    """Build the dependency list from a given depenency YAML node.

    A ``depends_on`` is used by test to establish their relationship. It looks
    like:

    :example:
        depends_on:
            ["list_of_test_name"]

    :param deps_node: the TE/job YAML node.
    :type deps_node: dict
    :param pkg_label: the label where this TE is from (to compute depnames)
    :type pkg_label: str
    :param pkg_prefix: the subtree where this TE is from (to compute depnames)
    :type pkg_prefix, str or NoneType

    :return: a list of dependencies, either as depnames or PManager objects
    :rtype: list
    """
    deps = list()
    for d in deps_node.get('depends_on', list()):
        deps.append(
            d if "/" in d else Test.compute_fq_name(pkg_label, pkg_prefix, d)
        )
    return deps


def build_pm_deps(deps_node):
    """Build the dependency list from a given YAML node.

    This only initialize package-manager oriented deps. For job deps, see
    ``build_job_deps``

    :param deps_node: contains package_manager YAML information
    :type deps_node: str
    :return: a list of PM objects, one for each entry
    :rtype: List[:class:`PManager`]
    """
    return pm.identify(deps_node.get('package_manager', {}))


class TEDescriptor:
    """A Test Descriptor (named TD, TE or TED), maps a test prograzm
    representation, as defined by a root node in a single test files.

    A TE Descriptor is not a test but a definition of a program (how to use it,
    to compile it...), leading to a collection once combined with a profile
    (providing on which MPI processes to run it, for instance).

    :ivar _te_name: YAML root node name, part of its unique id
    :type _te_name: str
    :ivar _te_label: which user directory this TE is coming from
    :type _te_label: str
    :ivar _te_subtree: subprefix, relative to label, where this TE is located
    :type _te_subtree: str or NoneType
    :ivar _full_name: fully-qualified te-name
    :type _full_name: str
    :ivar _srcdir: absolute path pointing to the YAML testfile dirname
    :type _srcdir: str
    :ivar _buildir: absolute path pointing to build equivalent of _srcdir
    :type _buildir: str
    :ivar _skipped: flag if this TE should be unfolded to tests or not
    :type _skipped: bool
    :ivar _effective_cnt: number of tests created by this single TE
    :type _effective_cnt: int
    :ivar _program_criterion: extra criterion defined by the TE
    :type _program_criterion: :class:`Criterion`
    :ivar others: used yaml node references.
    """

    @classmethod
    def init_system_wide(cls, base_criterion_name):
        """Initialize system-wide information (to shorten accesses).

        :param base_criterion_name: iterator name used as scheduling resource.
        :type base_criterion_name: str
        """
        cls._sys_crit = MetaConfig.root.get_internal('crit_obj')
        cls._base_it = base_criterion_name

    def __init__(self, name, node, label, subprefix):
        """constructor method.

        :param name: the TE name
        :type name: str
        :param node: the TE YAML content.
        :type node: str
        :param label: the user dir label.
        :type label: str
        :param subprefix: relative path between user dir & current TE testfile
        :type subprefix: str or NoneType

        :raises TDFormatError: Unproper YAML TE format (sanity check)
        """
        if not isinstance(node, dict):
            raise TestException.TestExpressionError(node)
        
        self._te_name = name
        self._skipped = name.startswith('.')
        self._te_label = label
        self._te_subtree = subprefix

        _, self._srcdir, _, self._buildir = testing.generate_local_variables(
            label,
            subprefix
        )
        # before doing anything w/ node:
        # arregate the 'group' definitions with the TE
        # to get all the fields in their final form
        if 'group' in node and node['group'] in MetaConfig.root.group.keys():
            tmp = MetaDict(MetaConfig.root.group[node['group']])
            tmp.update(MetaDict(node))
            node = tmp
        # load from descriptions
        self._build = MetaDict(node.get('build', None))
        self._run = MetaDict(node.get('run', None))
        self._validation = MetaDict(node.get('validate', None))
        self._artifacts = MetaDict(node.get('artifact', None))
        self._metrics = MetaDict(node.get('metric', None))
        self._attributes = MetaDict(node.get("attributes", None))
        self._template = node.get('group', None)
        self._debug = self._te_name+":\n"
        self._effective_cnt = 0
        self._tags = node.get('tag', list())

        path_prefix = self._buildir
        if self.get_attr('path_resolution', True) is False:
            path_prefix = ""

        for elt_k, elt_v in self._artifacts.items():
            if not os.path.isabs(elt_v):
                self._artifacts[elt_k] = os.path.join(path_prefix, elt_v)

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

    def get_attr(self, name, dflt=None):
        if name in self._attributes:
            return self._attributes[name]
        else:
            return dflt

    def _compatibility_support(self, compat):
        """Convert tricky keywords from old syntax too complex to be handled
        by the automatic converter.

        :param compat: dict of complex keyword extracted from old syntax.
        :param compat: dict or NoneType
        """
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
        
        if 'cflags' in self._build and 'sources' in self._build:
            self._build['sources']['cflags'] = self._build['cflags']
        if 'ldflags' in self._build and 'sources' in self._build:
            self._build['sources']['ldflags'] = self._build['ldflags']
        if 'params' in self._build.get('autotools', {}):
            self._build.autotools.args = self._build.autotools.params
        if 'vars' in self._build.get('cmake', {}):
            self._build.cmake.args = self._build.cmake.vars
        

    def _configure_criterions(self):
        """Prepare the list of components this TE will be built against.

        It consists in interesecting system-wide criterions and their
        definitions with this overriden criterion by this TE. The result is then
        what tests will be built on. If there is no intersection between
        system-wide and this TE declaration, the whole TE is skipped.
        """
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

                    cur_criterion.expand_values(v_sys)
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
        """How to create build tests from a collection of source files.

        :return: the command to be used.
        :rtype: str
        """
        lang = detect_source_lang(self._build.files)
        binary = self._te_name
        if self._build.sources.binary:
            binary = self._build.sources.binary
        elif self._run.program:
            binary = self._run.program

        self._build.sources.binary = binary

        program, args, envs = extract_compiler_config(lang, self._build.variants)
        
        command = "{cc} {cflags} {files} {ldflags} {args} {out}".format(
            cc=program,
            args=" ".join(args),
            cflags=self._build.sources.get('cflags', ''),
            files=" ".join(self._build.files),
            ldflags=self._build.sources.get('ldflags', ''),
            out="-o {}".format(os.path.join(self._buildir, binary))
        )
        return (command, envs)

    def __build_from_makefile(self):
        """How to create build tests from a Makefile.

        :return: the command to be used.
        :rtype: str
        """
        command = ["make"]
        basepath = self._srcdir

        # change makefile path if overriden by 'files'
        if 'files' in self._build:
            basepath = os.path.dirname(self._build.files[0])
            command.append("-f {}".format(" ".join(self._build.files)))

        compiler, args, envs = extract_compiler_config("cc", self._build.variants)
        # build the 'make' command
        command.append(
            '-C {path} {target} '.format(
                path=basepath,
                target=self._build.make.get('target', '')
            )
        )
        
        command += " ".join(self._build['make'].get('args', []))
        envs += self._build['make'].get('envs', [])

        return (" ".join(command), envs)

    def __build_from_cmake(self):
        """How to create build tests from a CMake project.

        :return: the command to be used.
        :rtype: str
        """
        command = ["cmake"]
        if 'files' in self._build:
            command.append(self._build.files[0])
        else:
            command.append(self._srcdir)
            
        _, args, envs = extract_compiler_config("cc", self._build.variants)
        command.append(
            r"-G 'Unix Makefiles' "
            r"-DCMAKE_BINARY_DIR='{build}' ".format(
                build=self._buildir
            )
        )

        command += self._build['cmake'].get('args', [])
        envs += self._build['cmake'].get('envs', [])

        self._build.files = [os.path.join(self._buildir, "Makefile")]
        tmp =  self.__build_from_makefile()
        next_command = tmp[0]
        envs += tmp[1]
        return (" && ".join([" ".join(command), next_command]), envs)

    def __build_from_autotools(self):
        """How to create build tests from a Autotools-based project.

        :return: the command to be used.
        :rtype: str
        """
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
            
        _, _, envs = extract_compiler_config("cc", self._build.variants)

        command.append(r"{configure} ".format(configure=configure_path))
        
        command += self._build['autotools'].get('args', [])
        envs += self._build['autotools'].get('envs', [])

        self._build.files = [os.path.join(self._buildir, "Makefile")]
        tmp = self.__build_from_makefile()
        next_command = tmp[0]
        envs += tmp[1]
        
        # TODO: why not creating another test, with a dep on this one ?
        return (" && ".join([" ".join(command), next_command]), envs)

    def __build_from_user_script(self):
        command = []
        env = []
        
        command = self._build.custom.get('program', 'echo')
        # args not relevant as cflags/ldflags can be used instead
        env = self._build.custom.get('envs', [])
        
        if not os.path.isabs(command):
            command = os.path.join(self._buildir, command)
            
        return (". {} && {}".format(os.path.join(MetaConfig.root.validation.output, pcvs.NAME_BUILD_CONF_SH), command), env)

    def __build_exec_process(self):
        """Drive compilation command generation based on TE format.

        :return: the command to be used.
        :rtype: str
        """
        if 'autotools' in self._build:
            return self.__build_from_autotools()
        elif 'cmake' in self._build:
            return self.__build_from_cmake()
        elif 'make' in self._build:
            return self.__build_from_makefile()
        elif 'custom' in self._build:
            return self.__build_from_user_script()
        else:
            return self.__build_from_sources()

    def __construct_compil_tests(self):
        """Meta-function steering compilation tests."""
        job_deps = []

        # ensure consistency when 'files' node is used
        # can be a list or a single value
        if 'files' in self._build:
            if not isinstance(self._build.files, list):
                self._build.files = [self._build.files]

            for i in range(0, len(self._build.files)):
                if not os.path.isabs(self._build.files[i]):
                    self._build.files[i] = os.path.join(
                        self._srcdir, self._build.files[i])

        # manage deps (tests, package_managers...)
        job_deps = build_job_deps(
            self._build, self._te_label, self._te_subtree)
        mod_deps = build_pm_deps(self._build)

        chdir = self._build.get('cwd')
        if chdir is not None and not os.path.isabs(chdir):
            chdir = os.path.abspath(os.path.join(self._buildir, chdir))

        tags = ["compilation"] + self._tags

        command, env = self.__build_exec_process()

        # count number of built tests
        self._effective_cnt += 1

        yield Test(
            te_name=self._te_name,
            user_suffix="cc" if self._run else None,
            label=self._te_label,
            subtree=self._te_subtree,
            command=command,
            environment=env,
            tags=tags,
            job_deps=job_deps,
            mod_deps=mod_deps,
            time=self._validation.time.get("mean", -1),
            delta=self._validation.time.get("tolerance", 0),
            kill_after=self._validation.time.get('kill_after', None),
            rc=self._validation.get("expect_exit", 0),
            artifacts=self._artifacts,
            analysis=self._validation.get("analysis", {}),
            resources=1,
            wd=chdir
        )

    def __construct_runtime_tests(self):
        """Generate tests to be run by the runtime command."""
        te_job_deps = build_job_deps(
            self._run, self._te_label, self._te_subtree)
        te_mod_deps = build_pm_deps(self._run)

        if self._build:
            fq_name = Test.compute_fq_name(
                self._te_label,
                self._te_subtree,
                self._te_name,
                'cc')
            if fq_name not in te_job_deps:
                te_job_deps.append(fq_name)

        # for each combination generated from the collection of criterions
        for comb in self._serie.generate():
            chdir = None

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


            clone_outdir = self.get_attr('copy_output', False)
            if clone_outdir:
                buildir = tempfile.mkdtemp(prefix="{}.".format(self._te_name), dir=self._buildir)
            else:
                buildir = self._buildir

            # attempt to determine test working directory
            chdir = self._run.cwd if self._run.cwd else buildir

            if not os.path.isabs(chdir):
                chdir = os.path.abspath(os.path.join(buildir, chdir))

            # keep the original value if user disabled prefix resolution
            if self.get_attr('path_resolution', True) is True:
                program = os.path.abspath(os.path.join(self._buildir, program))

            command = "{program} {params}".format(
                program=program,
                params=" ".join(params)
            )
            if self.get_attr('command_wrap', True) is True:
                command = "{runtime} {args} {runtime_args} {cmd}".format(
                    runtime=MetaConfig.root.runtime.get('program', ''),
                    runtime_args=MetaConfig.root.runtime.get('args', ''),
                    args=" ".join(args),
                    cmd=command
                )

            self._effective_cnt += 1

            yield Test(
                te_name=self._te_name,
                label=self._te_label,
                subtree=self._te_subtree,
                command=command,
                job_deps=te_job_deps,
                mod_deps=te_mod_deps,
                tags=self._tags,
                metrics=self._metrics,
                environment=env,
                dim=comb.get('n_node', 1),
                time=self._validation.time.get("mean", -1),
                delta=self._validation.time.get("tolerance", 0),
                kill_after=self._validation.time.get('kill_after', None),
                rc=self._validation.get("expect_exit", 0),
                valscript=self._validation.script.get('path', None),
                analysis=self._validation.get("analysis", {}),
                comb=comb,
                wd=chdir,
                artifacts=self._artifacts,
                matchers=self._validation.get('match', None)
            )

    def construct_tests(self):
        """Construct a collection of tests (build & run) from a given TE.

        This function will process a YAML node and, through a generator, will
        create each test coming from it.
        """
        # if this TE does not lead to a single test, skip now
        if self._skipped:
            return
        
        clone_indir = self.get_attr('copy_input', False)
    
        if clone_indir:
            isolation_path = tempfile.mkdtemp(prefix="{}.".format(self._te_name), dir=self._buildir)
            old_src_dir = self._srcdir
            self._srcdir = os.path.join(isolation_path, "src")
            shutil.copytree(old_src_dir, self._srcdir)
            self._buildir = os.path.join(isolation_path, "build")
            os.mkdir(self._buildir)
                
            
        if self._build:
            yield from self.__construct_compil_tests()
        if self._run:

            if self.get_attr('command_wrap', True) is False:
                self._serie = Serie({**self._program_criterion})
            else:
                self._serie = Serie(
                    {**self._criterion, **self._program_criterion})
            yield from self.__construct_runtime_tests()
            del self._serie

    def get_debug(self):
        """Build information debug for the current TE.

        :return: the debug info 
        :rtype: dict
        """
        # if the current TE did not lead to a single test, skip now
        if self._skipped:
            return {}

        self._debug_yaml = dict()

        # count actual tests built
        if self._run:
            # for system-wide iterators, count max number of possibilites
            for k, v in self._criterion.items():
                self._debug_yaml[k] = list(v.values)
                #real_cnt *= len(v.values)

            # for program-lavel iterators, count number of possibilies
            self._debug_yaml['program'] = dict()
            for k, v in self._program_criterion.items():
                self._debug_yaml['program'][k] = list(v.values)
                #user_cnt *= len(v.values)

        # store debug info
        #self._debug_yaml['.stats'] = {
        #    'theoric': user_cnt * real_cnt,
        #    'program_factor': user_cnt,
        #    'effective': self._effective_cnt
        #}

        return self._debug_yaml

    @property
    def name(self):
        """Getter to the current TE name.

        :return: te_name
        :rtype: str
        """
        return self._te_name

    def __repr__(self):
        """Internal TE representation, for auto-dumping.

        :return: the node representation.
        :rtype: str
        """
        return repr(self._build) + repr(self._run) + repr(self._validation)
