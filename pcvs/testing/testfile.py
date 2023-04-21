import tempfile
import re
import functools
import pprint
import getpass
import operator
import os
import pathlib
import subprocess

from pcvs.helpers.exceptions import ValidationException
from ruamel.yaml import YAML, YAMLError

from pcvs import PATH_INSTDIR, io, testing
from pcvs.helpers import system
from pcvs.helpers.exceptions import TestException
from pcvs.helpers.system import MetaConfig
from pcvs.plugins import Plugin
from pcvs.testing import tedesc


constant_tokens = None

def init_constant_tokens():
    """
    Initialize global tokens to be replaced.
    
    The dict is built from profile specifications. The exact location for this
    function is still to be determined.
    """
    global constant_tokens
    constant_tokens = {
        '@HOME@': str(pathlib.Path.home()),
        '@USER@': getpass.getuser(),
    }
    for comp, comp_node in MetaConfig.root.compiler.items():
        constant_tokens['@COMPILER_{}@'.format(comp.upper())] = comp_node.get('program', "")
        
    constant_tokens['@RUNTIME_PROGRAM@'] = MetaConfig.root.runtime.get('program', "")

def replace_special_token(content, src, build, prefix, list=False):
    output = []
    errors = []
    
    global constant_tokens
    if not constant_tokens:
        init_constant_tokens()
    
    if prefix is None:
        prefix = ""
    
    tokens = {
        **constant_tokens,
        '@BUILDPATH@': os.path.join(build, prefix),
        '@SRCPATH@': os.path.join(src, prefix),
        '@ROOTPATH@': src,
        '@BROOTPATH@': build,
        '@SPACKPATH@': "TBD",
    }
    
    r = re.compile("(?P<name>@[a-zA-Z0-9-_]+@)")
    for line in content.split('\n'):
        for match in r.finditer(line):
            
            name = match.group('name')
            if name not in tokens:
                errors.append(name)
            else:
                line = line.replace(name, tokens[name])
        output.append(line)

    if errors:
        raise ValidationException.WrongTokenError(invalid_tokens=errors)
    return "\n".join(output)


class TestFile:
    """A TestFile manipulates source files to be processed as benchmarks
(pcvs.yml & pcvs.setup).

    It handles global informations about source imports & building one execution
    script (``list_of_tests.sh``) per input file.

    :param _in: YAML input file
    :type _in: str
    :param _path_out: prefix where to store output artifacts 
    :type _path_out: str
    :param _raw: stream to populate the TestFile rather than opening input file
    :type _raw: dict
    :param _label: label the test file comes from
    :type _label: str
    :param _prefix: subtree the test file has been extracted
    :type _prefix: str
    :param _tests: list of tests handled by this file
    :type _tests: list
    :param _debug: debug instructions (concatenation of TE debug infos)
    :type _debug: dict
    """

    cc_pm_string = ""
    rt_pm_string = ""
    val_scheme = None

    def __init__(self, file_in, path_out, data=None, label=None, prefix=None):
        """Constructor method.

        :param file_in: input file
        :type file_in: str
        :param path_out: prefix to store artifacts
        :type path_out: str
        :param data: raw data to inject instead of opening input file
        :type data: dict
        :param label: label the TE is coming from
        :type label: str
        :param prefix: testfile Subtree (may be Nonetype)
        :type prefix: str
        """
        self._in = file_in
        self._path_out = path_out
        self._raw = data
        self._label = label
        self._prefix = prefix
        self._tests = list()
        self._debug = dict()
        if TestFile.val_scheme is None:
            TestFile.val_scheme = system.ValidationScheme('te')

    def load_from_file(self, f):
        with open(f, 'r') as fh:
            stream = fh.read()
            self.load_from_str(stream)

    def load_from_str(self, data):
        """Fill a File object from stream.

        This allows reusability (by loading only once).

        :param data: the YAML-formatted input stream.
        :type data: YAMl-formatted str
        """
        source, _, build, _ = testing.generate_local_variables(
            self._label, self._prefix)
        
        stream = replace_special_token(data, source, build, self._prefix)
        try:
            self._raw = YAML(typ='safe').load(stream)
        except YAMLError as e:
            raise ValidationException.FormatError(origin="<stream>")
    
    def save_yaml(self):
        src, _, build, curbuild = testing.generate_local_variables(
            self._label,
            self._prefix)
        
        with open(os.path.join(curbuild, "pcvs.setup.yml"), "w") as fh:
            YAML(typ='safe').dump(self._raw, fh)

    def validate(self, allow_conversion=True) -> bool:
        try:
            if self._raw:
                TestFile.val_scheme.validate(self._raw, filepath=self._in)
            return True
        except ValidationException.WrongTokenError as e:
            # Issues with replacing @...@ keys
            e.add_dbg(file=self._in)
            raise TestException.TestExpressionError(self._in, error=e)
        
        except ValidationException.FormatError as e:
            # YAML is valid but not following the Scheme
            # If YAML is invalid, load() functions will failed first
            
            # At first attempt, YAML are converted.
            # There is no second chance
            if not allow_conversion:
                e.add_dbg(file=self._in)
                raise e
            
            tmpfile = tempfile.mkstemp()[1]
            with open(tmpfile, 'w') as fh:
                YAML(typ='safe').dump(self._raw, fh)
            proc = subprocess.Popen(
                "pcvs_convert {} --stdout -k te --skip-unknown -t '{}'".format(
                    tmpfile,
                    os.path.join(PATH_INSTDIR, "templates/config/group-compat.yml")),
                stderr=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                shell=True)
            
            fds = proc.communicate()
            os.remove(tmpfile)
            if proc.returncode != 0:
                raise e
            converted_data = YAML(typ='safe').load(fds[0].decode('utf-8'))
            #keep only TE conversion
            # anything else is dropped when converting on-the-fly
            self._raw = converted_data
            self.validate(allow_conversion=False)
            io.console.warning("\t--> Legacy syntax for: {}".format(self._in))
            io.console.warning("Please consider updating it with `pcvs_convert -k te`")
            return False

    @property
    def nb_descs(self):
        if self._raw is None:
            return 0
        return len(self._raw.keys())

    def process(self):
        """Load the YAML file and map YAML nodes to Test()."""
        src, _, build, _ = testing.generate_local_variables(
            self._label,
            self._prefix)

        # if file hasn't be loaded yet
        if self._raw is None:
            self.load_from_file(self._in)
            
        self.validate()

        # main loop, parse each node to register tests
        for k, content, in self._raw.items():
            MetaConfig.root.get_internal(
                "pColl").invoke_plugins(Plugin.Step.TDESC_BEFORE)
            if content is None:
                # skip empty nodes
                continue
            td = tedesc.TEDescriptor(k, content, self._label, self._prefix)
            for test in td.construct_tests():
                self._tests.append(test)
            io.console.info("{}: {}".format(td.name, pprint.pformat(td.get_debug())))

            MetaConfig.root.get_internal(
                "pColl").invoke_plugins(Plugin.Step.TDESC_AFTER)

            # register debug informations relative to the loaded TEs
            self._debug[k] = td.get_debug()

    def flush_sh_file(self):
        """Store the given input file into their destination."""
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
            fh_sh.write("""#!/bin/sh
if test -n "{simulated}"; then
    PCVS_SHOW=1
    PCVS_SHOW_ENV=1
    PCVS_SHOW_MOD=1
    PCVS_SHOW_CMD=1
fi

if test -z "$PCVS_SHOW"; then
eval "{pm_string}"
elif test -n "$PCVS_SHOW_MOD"; then
test -n "$PCVS_VERBOSE" && echo "## MODULE LOADED FROM PROFILE ##"
cat<<EOF
{pm_string}
EOF
#else... SHOW but not this option --> nothing to do

fi

for arg in "$@"; do case $arg in
""".format(simulated="sim" if MetaConfig.root.validation.simulated is True else "",
                pm_string="\n".join([
                        TestFile.cc_pm_string,
                        TestFile.rt_pm_string
                        ])))

            for test in self._tests:
                fh_sh.write(test.generate_script(fn_sh))
                MetaConfig.root.get_internal('orchestrator').add_new_job(test)

            fh_sh.write("""
        --list) printf "{list_of_tests}\\n"; exit 0;;
        *) printf "Invalid test-name \'$arg\'\\n"; exit 1;;
        esac
    done
    
    if test -z "$PCVS_SHOW"; then
        eval "${{pcvs_load}}" || exit "$?"
        eval "${{pcvs_env}}" || exit "$?"
        eval "${{pcvs_cmd}}" || exit "$?"
        exit $?
    else   
        if test -n "$PCVS_SHOW_MOD"; then
            test -n "$PCVS_VERBOSE" && echo "#### MODULE LOADED ####"
cat<<EOF
${{pcvs_load}}
EOF
        fi
        
        if test -n "$PCVS_SHOW_ENV"; then
        test -n "$PCVS_VERBOSE" && echo "###### SETUP ENV ######"
cat<<EOF
${{pcvs_env}}
EOF
        fi
        if test -n "$PCVS_SHOW_CMD"; then
        test -n "$PCVS_VERBOSE" && echo "##### RUN COMMAND #####"
cat<<EOF
${{pcvs_cmd}}
EOF
        fi
    fi
    exit $?\n""".format(list_of_tests="\n".join([
                t.name
                for t in self._tests
            ])))

        self.generate_debug_info()

    def generate_debug_info(self):
        """Dump debug info to the appropriate file for the input object."""
        if len(self._debug) and io.console.verb_debug:
            with open(os.path.join(self._path_out, "dbg-pcvs.yml"), 'w') as fh:
                # compute max number of combinations from system iterators
                sys_cnt = functools.reduce(
                    operator.mul,
                    [
                        len(v['values'])
                        for v in MetaConfig.root.criterion.values()
                    ]
                )
                self._debug.setdefault('.system-values', {})
                self._debug['.system-values'].setdefault('stats', {})

                for c_k, c_v in MetaConfig.root.criterion.items():
                    self._debug[".system-values"][c_k] = c_v['values']
                self._debug[".system-values"]['stats']['theoric'] = sys_cnt
                yml = YAML(typ='safe')
                yml.default_flow_style = None
                yml.dump(self._debug, fh)
