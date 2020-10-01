import os
import copy
import yaml
import pprint
import pathlib
import functools
import operator
import subprocess
from addict import Dict

from pcvsrt.helpers import io, log, lowtest, system
from pcvsrt.criterion import Criterion, Serie


def __load_yaml_file_legacy(f):
    # barely legal to do that...
    old_group_file = os.path.join(io.ROOTPATH, "templates/group-compat.yml")
    cmd = "pcvs_convert {} --stdout -k te -t {} 2>/dev/null".format(f, old_group_file)
    out = subprocess.check_output(cmd, shell=True)
    return out.decode('utf-8')


def load_yaml_file(f, s, b, p):
    convert = False
    obj = {}
    try:
        with open(f, 'r') as fh:
            stream = fh.read()
            stream = replace_yaml_token(stream, s, b, p)
            obj = yaml.load(stream, Loader=yaml.FullLoader)

        # TODO: Validate input & raise YAMLError if invalid
        #raise yaml.YAMLError("TODO: write validation")
    except yaml.YAMLError:
        log.err("Yolo")
        convert = True
    except Exception as e:
        log.err("Err loading the YAML file {}:".format(f), "{}".format(e), abort=1)

    if convert:
        log.debug("Attempt to use legacy syntax for {}".format(f))
        obj = yaml.load(__load_yaml_file_legacy(f), Loader=yaml.FullLoader)
        if log.get_verbosity('debug'):
            convert_file = os.path.join(os.path.split(f)[0], "convert-pcvs.yml")
            log.debug("Save converted file to {}".format(convert_file))
            with open(convert_file, 'w') as fh:
                yaml.dump(obj, fh)
    return obj

def replace_yaml_token(stream, src, build, prefix):
    tokens = {
        '@BUILDPATH@': os.path.join(build, prefix),
        '@SRCPATH@': os.path.join(src, prefix),
        '@ROOTPATH@': src,
        '@BROOTPATH@': build,
        '@SPACKPATH@': "TBD",
        '@HOME@': str(pathlib.Path.home()),
        '@USER@': os.getlogin()
    }
    for k, v in tokens.items():
        stream = stream.replace(k, v)
    return stream


class TestFile:
    def __init__(self, file_in, path_out, data=None, label=None, subprefix=None):
        self._in = file_in
        self._path_out = path_out
        self._raw = data
        self._label = label
        self._prefix = subprefix
        self._tests = list()
        self._debug = dict()

    def start_process(self):
        src, _, build, _ = io.generate_local_variables(self._label, self._prefix)
        
        if self._raw is None:
            self._raw = load_yaml_file(self._in, src, build, self._prefix)
            
        #self._raw = replace_yaml_token(self._raw, src, build, self._prefix)
        for k, content, in self._raw.items():
            td = TEDescriptor(k, content, self._label, self._prefix)
            for test in td.construct_tests():
                self._tests.append(test)
            
            self._debug[k] = td.get_debug()

            self._tests += []
    
    def flush_xml_to_disk(self):
        fn = os.path.join(self._path_out, "list_of_tests.xml")
        with open(fn, 'w') as fh:
            fh.write("<jobSuite>")
            for test in self._tests:
                fh.write(test.serialize_xml())
            fh.write("</jobSuite>")
        
        if len(self._debug) and system.get('validation').verbose:
            with open(os.path.join(self._path_out, "dbg-pcvs.yml"), 'w') as fh:
                sys_cnt = functools.reduce(operator.mul, [len(v['values']) for v in system.get('criterion').iterators.values()])
                self._debug['.system-values'] = dict()
                self._debug['.system-values']['stats'] = dict()
                for c_k, c_v in system.get('criterion').iterators.items():
                    self._debug[".system-values"][c_k] = c_v['values']
                self._debug[".system-values"]['stats']['theoric'] = sys_cnt

                yaml.dump(self._debug, fh, default_flow_style=None)
        return fn

    def flush_to_disk(self):
        return self.flush_xml_to_disk()


class Test:
    """A basic test representation, from one step to concretize the logic
    to the JCHRONOSS input datastruct."""
    def __init__(self, **kwargs):
        """register a new test"""
        self._array = kwargs
    
    def serialize_xml(self):
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
        string += "{}".format(lowtest.xml_setif(self._array, 'postscript', 'postCommand'))
        string += "<constraints>{}</constraints>".format(
            lowtest.xml_setif(self._array, 'constraint'))
        string += "</job>"
        return string

    def serialize_shell(self):
        pass
    

class TEDescriptor:
    """Maps to a program description, as read by YAML user files"""
    @classmethod
    def init_system_wide(cls, base_criterion_name):
        """Initialize system-wide information (to shorten accesses)"""
        cls._sys_crit = system.get('critobj').iterators
        cls._base_it = base_criterion_name

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
        self._debug = self._te_name+":\n"
        self._effective_cnt = 0

        self._full_name = ".".join([self._te_pkg, self._te_name])
        
        self._configure_criterions()
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
            for k, elt in self._program_criterion.items():
                elt.expand_values()


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

        binary = self._te_name
        if self._build.sources.binary:
            binary = self._build.sources.binary
        elif self._run.program:
            binary = self._run.program
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

        self._effective_cnt += 1

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

        # for each combination generated from the collection of criterions
        for comb in self.serie.generate():
            deps = [self._full_name] if self._build else []
            for d in self._run.get('depends_on', []):
                deps.append(d if '.' in d else ".".join([self._te_pkg, d]))

            envs, args, params = comb.translate_to_command()
            program = self._te_name
            if self._run.program:
                program = self._run.program
            elif self._build.sources.binary:
                program = self._build.sources.binary

            command = [
                " ".join(envs),
                system.get('runtime').program,
                " ".join(args),
                os.path.join(self._buildir, program),
                " ".join(params)
            ]

            self._effective_cnt+=1

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

    def get_debug(self):
        user_cnt = functools.reduce(operator.mul, [len(v.values) for v in self._program_criterion.values()])
        real_cnt = functools.reduce(operator.mul, [len(v.values) for v in self._criterion.values()])
        self._debug_yaml = dict()
        
        for k, v in self._criterion.items():   
            self._debug_yaml[k] = list(v.values)
        print(self._debug_yaml)
        self._debug_yaml['.stats'] = {
                'theoric': user_cnt * real_cnt,
                'program_factor': user_cnt,
                'effective': self._effective_cnt
        }
        return self._debug_yaml

    def __repr__(self):
        """internal representation, for auto-dumping"""
        return repr(self._build) + repr(self._run) + repr(self._validation)
