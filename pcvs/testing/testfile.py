import functools
import getpass
import operator
import os
import pathlib
import subprocess

import jsonschema
from ruamel.yaml import YAML, YAMLError

from pcvs import PATH_INSTDIR
from pcvs.helpers import log, system, utils
from pcvs.helpers.exceptions import TestException
from pcvs.helpers.system import MetaConfig
from pcvs.plugins import Plugin
from pcvs.testing import tedesc


def __load_yaml_file_legacy(f):
    """Legacy version to load a YAML file.

    This function intends to be backward-compatible with old YAML syntax
    by relying on external converter (not perfect).

    :raises DynamicProcessError: the setup script cannot be executed properly
    :param f: old-syntax YAML filepath
    :type f: str
    :return: new-syntax YAML stream
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
        raise TestException.DynamicProcessError(f)

    return fds[0].decode('utf-8')


def replace_special_token(stream, src, build, prefix):
    """Replace placeholders by their actual definition in a stream.

    :param stream: the stream to alter
    :type stream: str
    :param src: source directory (replace SRCPATH)
    :type src: str
    :param build: build directory (replace BUILDPATH)
    :type build: str
    :param prefix: subtree for the current parsed stream
    :type prefix: str
    :return: the modified stream
    :rtype: str
    """

    if prefix is None:
        prefix = ""
    tokens = {
        '@BUILDPATH@': os.path.join(build, prefix),
        '@SRCPATH@': os.path.join(src, prefix),
        '@ROOTPATH@': src,
        '@BROOTPATH@': build,
        '@SPACKPATH@': "TBD",
        '@HOME@': str(pathlib.Path.home()),
        '@USER@': getpass.getuser()
    }
    for k, v in tokens.items():
        stream = stream.replace(k, v)
    return stream


def load_yaml_file(f, source, build, prefix):
    """Load a YAML test description file.

    :param f: YAML-based source testfile
    :type f: str
    :param source: source directory (used to replace placeholders)
    :type source: str
    :param build: build directory (placeholders)
    :type build: str
    :param prefix: file subtree (placeholders)
    :type prefix: str
    :return: the YAML-to-dict content
    :rtype: dict
    """
    need_conversion = False
    obj = {}
    try:
        with open(f, 'r') as fh:
            stream = fh.read()
            stream = replace_special_token(stream, source, build, prefix)
            obj = YAML(typ='safe').load(stream)
    # badly formatted YAML
    except YAMLError:
        need_conversion = True

    # attempt to convert of the fly the YAML file
    if need_conversion:
        log.manager.debug("\t--> Legacy syntax: {}".format(f))
        obj = YAML(typ='safe').load(__load_yaml_file_legacy(f))

        # when 'debug' is activated, print the converted YAML file
        if log.manager.has_verb_level('debug'):
            cv_file = os.path.join(os.path.split(f)[0], "converted-pcvs.yml")
            log.manager.debug("\t--> Stored file to {}".format(cv_file))
            with open(cv_file, 'w') as fh:
                YAML(typ='safe').dump(obj, fh)
    return obj


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

    def load_from_str(self, data):
        """Fill a File object from stream.

        This allows reusability (by loading only once).

        :param data: the YAML-formatted input stream.
        :type data: YAMl-formatted str
        """
        source, _, build, _ = utils.generate_local_variables(
            self._label, self._prefix)
        stream = replace_special_token(data, source, build, self._prefix)
        self._raw = YAML(typ='safe').load(stream)

    def process(self):
        """Load the YAML file and map YAML nodes to Test()."""
        src, _, build, _ = utils.generate_local_variables(
            self._label,
            self._prefix)

        if self._raw is None:
            self._raw = load_yaml_file(self._in, src, build, self._prefix)
        # this check should also be used while loading the file.
        # (old syntax files will only be converted if they are wrongly
        # formatted, not if they are invalid)
        try:
            TestFile.val_scheme.validate(self._raw, filepath=self._in)
        except jsonschema.ValidationError as e:
            self._debug['.yaml_errors'].append(e)

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

            MetaConfig.root.get_internal(
                "pColl").invoke_plugins(Plugin.Step.TDESC_AFTER)

            # register debug informations relative to the loaded TEs
            #self._debug[k] = td.get_debug()

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
test -n '{simulated}' && PCVS_SHOW='all'
if test -n "$PCVS_SHOW"; then
    test "$PCVS_SHOW" = "all" -o "$PCVS_SHOW" = "loads" && echo '{pm_string}'
else
    {pm_string}
    :
fi
for arg in "$@"; do case $arg in
""".format(simulated="sim" if MetaConfig.root.validation.simulated is True else "",
                pm_string="#Package-manager set by profile: \n"+"\n".join([
                        TestFile.cc_pm_string,
                        TestFile.rt_pm_string
                        ])))

            for test in self._tests:
                fh_sh.write(test.generate_script(fn_sh))
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
        """Dump debug info to the appropriate file for the input object."""
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
                yml = YAML(typ='safe')
                yml.default_flow_style = None
                yml.dump(self._debug, fh)
