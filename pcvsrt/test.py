import os
import copy
import yaml
import pprint
from addict import Dict

from pcvsrt.helpers import io, log, lowtest, system
from pcvsrt.criterion import Criterion, Serie


class Test:
    """A basic test representation, from one step to concretize the logic
    to the JCHRONOSS input datastruct."""
    def __init__(self, **kwargs):
        """register a new test"""
        self._array = kwargs
    
    def serialize(self):
        """Serialize the test to the logic: currently an XML node"""
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
        string += "<constraints>{}</constraints>".format(
            lowtest.xml_setif(self._array, 'constraint'))
        string += "</job>"
        return string

    @staticmethod
    def finalize_file(path, package, content):
        """Once a serie of tests, to be packaged together, has been
        serialized, this static function will complete the stream by writing
        down the logic to the proper file
        
        TODO: Maybe do this through a script callable by tests"""
        fn = os.path.join(path, "list_of_tests.xml")
        with open(fn, 'w') as fh:
            fh.write("<jobSuite>")
            fh.write(content)
            fh.write("</jobSuite>")
        return fn


class TEDescriptor:
    """Maps to a program description, as read by YAML user files"""
    @classmethod
    def init_system_wide(cls, base_criterion_name):
        """Initialize system-wide information (to shorten accesses)"""
        cls._sys_crit = system.get('critobj').iterators
        cls._base_it = base_criterion_name
        cls._nb_instances = 0
    
    @classmethod
    def get_nb_instances(cls):
        return cls._nb_instances

    def __init__(self, name, node, label, subprefix):
        """load a new TEDescriptor from a given YAML node"""
        if not isinstance(node, dict):
            log.err(
                "Unable to build a TestDescriptor "
                "from the given node (got {})".format(type(node)), abort=1)
        self._te_name = name
        self._skipped = name.startswith('.')
        self._te_label = node.get('label', self._te_name)
        self._te_pkg = ".".join([label, subprefix.replace('/', '.')]) if subprefix else label
        
        _, self._srcdir, _, self._buildir = io.generate_local_variables(label, subprefix)

        # before doint anything w/ node:
        # arregate the 'group' definitions with the TE
        # to get all the fields in their final form
        if 'group' in node:
            assert(node['group'] in system.get('group').keys())
            tmp = Dict(system.get('group')[node['group']])
            tmp.update(Dict(node))
            node = tmp
        self._build = Dict(node.get('build', None))
        self._run = Dict(node.get('run', None))

        if 'program' in self._run.get('iterate', {}):
            self._program_criterion = {k: Criterion(k, v, local=True) for k, v in self._run.iterate.program.items()}
        else:
            self._program_criterion = {}

        self._validation = Dict(node.get('validate', None))
        self._artifacts = Dict(node.get('artifacts', None))
        self._template = node.get('group', None)

        self._full_name = ".".join([self._te_pkg, self._te_name])
        
        self._configure_criterions()
        self._compatibility_support(node.get('_compat', None))
        TEDescriptor._nb_instances += 1

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
                        log.debug("No valid intersection found for '{}, Discard".format(k_sys))
                        self._skipped = True
                    else:
                        tmp[k_sys] = cur_criterion
                else:  # key is not overriden
                    tmp[k_sys] = v_sys

            self._criterion = tmp
            # now build program iterators
            [elt.expand_values() for elt in self._program_criterion.values()]  

    def __build_from_sources(self):
        """Specific to build rule, where the compilation is made from a
        collection of source files"""
        command = list()
        lang = lowtest.detect_source_lang(self._build.files)
        command.append(system.get('compiler').commands.get(lang, 'echo'))
        command.append(lowtest.prepare_cmd_build_variants(self._build.variants))
        command.append('{}'.format(self._build.get('cflags', '')))
        command.append('{}'.format(" ".join(self._build.files)))
        command.append('{}'.format(self._build.get('ldflags', '')))

        binary = self._build.sources.binary if 'binary' in self._build.sources else self._te_name
        command.append('-o {}'.format(os.path.join(self._buildir, binary)))
        # save it
        self._build.sources.binary = binary

        if 'cwd' in self._build:
            command.insert(0, "cd {} &&".format(self._build.cwd))
        
        return " ".join(command)

    def __build_from_makefile(self):
        """Specific to build rule, where the compilation is managed by 
        a makefile"""
        command = ["make"]
        if 'files' in self._build:
            basepath = os.path.dirname(self._build.files[0])
            command.append("-f {}".format(" ".join(self._build.files)))
        else:
            basepath = self._srcdir
        
        command.append("-C {}".format(basepath))
        command.append("{}".format(self._build.make.get('target', '')))
        command.append('PCVS_CC="{}"'.format(system.get('compiler').commands.get('cc', '')))
        command.append('PCVS_CXX="{}"'.format(system.get('compiler').commands.get('cxx', '')))
        command.append('PCVS_CU="{}"'.format(system.get('compiler').commands.get('cu', '')))
        command.append('PCVS_FC="{}"'.format(system.get('compiler').commands.get('fc', '')))
        command.append('PCVS_CFLAGS="{} {}"'.format(
            lowtest.prepare_cmd_build_variants(self._build.variants),
            self._build.get('cflags', '')
        ))
        command.append('PCVS_LDFLAGS="{}"'.format(self._build.get('ldflags', '')))
        return " ".join(command)

    def __construct_compil_tests(self):
        """Meta-function steering compilation tests"""
        deps = []
        
        # ensure consistency when 'files' node is used
        if not isinstance(self._build.files, list):
            self._build.files = [self._build.files]

        # a  'make' node prevails
        if 'make' in self._build:
            command = self.__build_from_makefile()
        else:
            command = self.__build_from_sources()
            
        try:
            # collect dependencies
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
        """function steering tests to be run by the runtime command"""
        #TODO: handle runtime filters (dynamic import)

        # for each combination generated from the collection of criterions
        for comb in self.serie.generate():
            deps = [self._full_name] if self._build else []
            for d in self._run.get('depends_on', []):
                deps.append(d if '.' in d else ".".join([self._te_pkg, d]))

            envs, args, params = comb.translate_to_command()
            program = self._run.program if 'program' in self._run else self._te_name
            command = [
                " ".join(envs),
                system.get('runtime').program,
                " ".join(args),
                os.path.join(self._buildir, program),
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
        if self._skipped:
            return

        """Meta function to triggeer test construction"""
        self.serie = Serie({**self._criterion, **self._program_criterion})
        if self._build:
            yield from self.__construct_compil_tests()
        if self._run:
            yield from self.__construct_runtime_tests()

    def __repr__(self):
        """internal representation, for auto-dumping"""
        return repr(self._build) + repr(self._run) + repr(self._validation)
