import base64
import os
import subprocess
import tempfile

import jsonschema
import yaml
from addict import Dict
from prettytable import PrettyTable

from pcvs.backend import config, profile, run
from pcvs.helpers import log, system, utils
from pcvs.helpers.exceptions import ValidationException


def locate_scriptpaths(output=None):
    """Path lookup to find all 'list_of_tests' script within a given prefix.

    :param output: prefix to walk through, defaults to current directory
    :type output: str, optional
    """
    if output is None:
        output = os.getcwd()
    scripts = list()
    for root, _, files in os.walk(output):
        for f in files:
            if f == 'list_of_tests.sh':
                scripts.append(os.path.join(root, f))
    return scripts


def compute_scriptpath_from_testname(testname, output=None):
    """Locate the proper 'list_of_tests.sh' according to a fully-qualified test
    name.

    :param testname: test name belonging to the script
    :type testname: str
    :param output: prefix to walk through, defaults to current directory
    :type output: str, optional

    """
    if output is None:
        output = os.getcwd()

    buildir = utils.find_buildir_from_prefix(output)
    prefix = os.path.dirname(testname)
    return os.path.join(
        buildir,
        'test_suite',
        prefix,
        "list_of_tests.sh"
    )


def process_check_configs():
    """Analyse available configurations to ensure their correctness relatively
    to their respective schemes."""
    errors = dict()
    t = PrettyTable()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"

    for kind in config.CONFIG_BLOCKS:
        for scope in utils.storage_order():
            for blob in config.list_blocks(kind, scope):
                token = log.manager.utf('fail')
                err_msg = ""
                obj = config.ConfigurationBlock(kind, blob[0], scope)
                obj.load_from_disk()

                try:
                    obj.check()
                    token = log.manager.utf('succ')
                except jsonschema.exceptions.ValidationError as e:
                    err_msg = base64.b64encode(str(e.message).encode('utf-8'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                    log.manager.debug(str(e))

                t.add_row([token, obj.full_name])
    print(t)
    return errors


def process_check_profiles():
    """Analyse availables profiles and check their correctness relatively to the
    base scheme."""
    t = PrettyTable()
    errors = dict()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"

    for scope in utils.storage_order():
        for blob in profile.list_profiles(scope):
            token = log.manager.utf('fail')
            obj = profile.Profile(blob[0], scope)
            obj.load_from_disk()
            try:
                obj.check()
                token = log.manager.utf('succ')
            except jsonschema.exceptions.ValidationError as e:
                err_msg = base64.b64encode(str(e.message).encode('utf-8'))
                errors.setdefault(err_msg, 0)
                errors[err_msg] += 1
                log.manager.debug(str(e))

            t.add_row([token, obj.full_name])
    print(t)
    return errors


def process_check_setup_file(filename, prefix):
    """Check if a given pcvs.setup could be parsed if used in a regular process.

    :param filename: the pcvs.setup filepath
    :type filename: str
    :param prefix: the subtree the setup is extract from (used as argument)
    :type prefix: str
    :return: a tuple (err msg, icon to print, parsed data)
    :rtype: tuple
    """
    err_msg = None
    token = log.manager.utf('fail')
    data = None
    env = os.environ
    env.update(run.build_env_from_configuration({}))
    try:
        tdir = tempfile.mkdtemp()
        with utils.cwd(tdir):
            env['pcvs_src'] = os.path.dirname(filename).replace(prefix, '')
            env['pcvs_testbuild'] = tdir
            if not os.path.isdir(os.path.join(tdir, prefix)):
                os.makedirs(os.path.join(tdir, prefix))
            proc = subprocess.Popen(
                [filename, prefix], env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            fds = proc.communicate()
            if fds[1]:
                err_msg = base64.b64encode(fds[1])
            else:
                data = fds[0].decode('utf-8')
                token = log.manager.utf('succ')
    except subprocess.CalledProcessError as e:
        err_msg = base64.b64encode(str(e.stderr).encode('utf-8'))

    return (err_msg, token, data)


scheme = system.ValidationScheme('te')


def process_check_yaml_stream(data):
    """Analyze a pcvs.yml stream and check its correctness relatively to
    standard. 
    :param data: the stream to process
    :type data: str
    """
    global scheme
    token_load = token_yaml = "{}".format(log.manager.utf('fail'))
    err_msg = None
    try:
        stream = yaml.safe_load(data)
        token_load = "{}".format(log.manager.utf('succ'))

        scheme.validate(stream)
        token_yaml = "{}".format(log.manager.utf('succ'))

    except yaml.YAMLError as e:
        err_msg = base64.b64encode(str(e).encode('utf-8'))
    except ValidationException.FormatError as e:
        err_msg = base64.b64encode(str(e).encode('utf-8'))

    return (err_msg, token_load, token_yaml)


def process_check_directory(dir):
    """Analyze a directory to ensure defined test files are valid.

    :param dir: the directory to process.
    :type dir: str
    """
    errors = dict()
    setup_files, yaml_files = run.find_files_to_process(
        {os.path.basename(dir): dir})

    if setup_files:
        log.manager.print_section(
            'Analyzing scripts: (script{s}YAML{s}valid)'.format(s=log.manager.utf('sep_v')))
        for _, subprefix, f in setup_files:
            token_script = token_load = token_yaml = log.manager.utf('fail')
            err, token_script, data = process_check_setup_file(
                os.path.join(dir, subprefix, f), subprefix)
            if err:
                errors.setdefault(err, 0)
                errors[err] += 1
            else:
                err, token_load, token_yaml = process_check_yaml_stream(data)

                if err:
                    errors.setdefault(err, 0)
                    errors[err] += 1
            log.manager.print_item(' {}{}{}{}{} {}'.format(
                token_script,
                log.manager.utf('sep_v'),
                token_load,
                log.manager.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)
            ), with_bullet=False)

            if err:
                log.manager.info("FAILED: {}".format(
                    base64.b64decode(err).decode('utf-8')))

    if yaml_files:
        log.manager.print_section(
            "Analysis: pcvs.yml* (YAML{}Valid)".format(log.manager.utf('sep_v')))
        for _, subprefix, f in yaml_files:
            with open(os.path.join(dir, subprefix, f), 'r') as fh:
                err, token_load, token_yaml = process_check_yaml_stream(
                    fh.read())
                if err:
                    errors.setdefault(err, 0)
                    errors[err] += 1

            log.manager.print_item(' {}{}{} {}'.format(
                token_load,
                log.manager.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)), with_bullet=False)

            if err:
                log.manager.info("FAILED: {}".format(
                    base64.b64decode(err).decode('utf-8')))
    return errors


class BuildSystem:
    def __init__(self, root, dirs=None, files=None):
        self._root = root
        self._dirs = dirs
        self._files = files
        self._stream = Dict()

    def __append_listdir(self):
        self._dirs = list()
        self._files = list()
        for f in os.listdir(self._root):
            if os.path.isdir(f):
                self._dirs.append(f)
            else:
                self._files.append(f)

    def fill(self):
        pass

    def generate_file(self, filename="pcvs.yml"):
        out_file = os.path.join(self._root, filename)
        if os.path.isfile(out_file):
            log.manager.warn("template already exist ! Skip.")
            return

        with open(out_file, 'w') as fh:
            yaml.safe_dump(self._stream.to_dict(), fh)


class AutotoolsBuildSystem(BuildSystem):
    def fill(self):
        name = os.path.basename(self._root)
        self._stream[name].build.autotools.autogen = (
            'autogen.sh' in self._files)
        self._stream[name].build.files = os.path.join(self._root, 'configure')
        self._stream[name].build.autotools.params = ""


class CMakeBuildSystem(BuildSystem):
    def fill(self):
        name = os.path.basename(self._root)
        self._stream[name].build.cmake.vars = "CMAKE_BUILD_TYPE=Debug"
        self._stream[name].build.files = os.path.join(
            self._root, 'CMakeLists.txt')


class MakefileBuildSystem(BuildSystem):
    def fill(self):
        name = os.path.basename(self._root)
        self._stream[name].build.make.target = ''
        self._stream[name].build.files = os.path.join(self._root, 'Makefile')


def process_autotools_suite(root, dirs, files):
    stream = Dict()
    name = os.path.basename(root)
    stream[name].build.files = os.path.join(root, "configure")
    stream[name].build.autogen = ('autogen.sh' in files)


def process_discover_directory(path):

    for root, dirs, files in os.walk(path):
        obj = None
        if 'configure' in files:
            n = log.manager.style("Autotools", fg="yellow", bold=True)
            obj = AutotoolsBuildSystem(root, dirs, files)
        if 'CMakeLists.txt' in files:
            n = log.manager.style("CMake", fg="cyan", bold=True)
            obj = CMakeBuildSystem(root, dirs, files)
        if 'Makefile' in files:
            n = log.manager.style("Make", fg="red", bold=True)
            obj = MakefileBuildSystem(root, dirs, files)

        if obj is not None:
            dirs[:] = []
            log.manager.print_item("{} [{}]".format(root, n))
            obj.fill()
            obj.generate_file(filename="pcvs.yml")
