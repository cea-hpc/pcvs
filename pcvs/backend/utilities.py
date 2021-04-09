import base64
import os
import subprocess
import tempfile
from addict import Dict
import jsonschema
import yaml
from prettytable import PrettyTable

from pcvs import NAME_BUILDIR
from pcvs.backend import config, profile, run
from pcvs.helpers import log, utils, system
from pcvs.helpers.log import utf


def locate_scriptpaths(output=None):
    if output is None:
        output = os.path.join(os.getcwd(), NAME_BUILDIR, "test_suite")
    scripts = list()
    for root, _, files in os.walk(output):
        for f in files:
            if f == 'list_of_tests.sh':
                scripts.append(os.path.join(root, f))
    return scripts


def compute_scriptpath_from_testname(testname, output=None):
    if output is None:
        output = os.path.join(os.getcwd(), NAME_BUILDIR, "test_suite")
    prefix = os.path.dirname(testname)
    return os.path.join(
        output,
        prefix,
        "list_of_tests.sh"
    )


def process_check_configs():
    errors = dict()
    t = PrettyTable()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"

    for kind in config.CONFIG_BLOCKS:
        for scope in utils.storage_order():
            for blob in config.list_blocks(kind, scope):
                token = log.utf('fail')
                err_msg = ""
                obj = config.ConfigurationBlock(kind, blob[0], scope)
                obj.load_from_disk()

                try:
                    obj.check(fail=False)
                    token = log.utf('succ')
                except jsonschema.exceptions.ValidationError as e:
                    err_msg = base64.b64encode(str(e.message).encode('utf-8'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                    log.debug(str(e))

                t.add_row([token, obj.full_name])
    print(t)
    return errors


def process_check_profiles():
    t = PrettyTable()
    errors = dict()
    t.field_names = ["Valid", "ID"]
    t.align['ID'] = "l"

    for scope in utils.storage_order():
        for blob in profile.list_profiles(scope):
            token = log.utf('fail')
            obj = profile.Profile(blob[0], scope)
            obj.load_from_disk()
            try:
                obj.check(fail=False)
                token = log.utf('succ')
            except jsonschema.exceptions.ValidationError as e:
                err_msg = base64.b64encode(str(e.message).encode('utf-8'))
                errors.setdefault(err_msg, 0)
                errors[err_msg] += 1
                log.debug(str(e))

            t.add_row([token, obj.full_name])
    print(t)
    return errors


def process_check_setup_file(filename, prefix):
    err_msg = None
    token = utf('fail')
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
                token = log.utf('succ')
    except subprocess.CalledProcessError as e:
        err_msg = base64.b64encode(str(e.stderr).encode('utf-8'))

    return (err_msg, token, data)


scheme = system.ValidationScheme('te')


def process_check_yaml_stream(data):
    global scheme
    token_load = token_yaml = "{}".format(utf('fail'))
    err_msg = None
    try:
        stream = yaml.load(data, Loader=yaml.FullLoader)
        token_load = "{}".format(utf('succ'))

        scheme.validate(stream, fail_on_error=False)
        token_yaml = "{}".format(utf('succ'))

    except yaml.YAMLError as e:
        err_msg = base64.b64encode(str(e).encode('utf-8'))
    except jsonschema.exceptions.ValidationError as e:
        err_msg = base64.b64encode(str(e.message).encode('utf-8'))

    return (err_msg, token_load, token_yaml)


def process_check_directory(dir):
    errors = dict()
    setup_files, yaml_files = run.find_files_to_process(
        {os.path.basename(dir): dir})

    if setup_files:
        log.print_section(
            'Analyzing scripts: (script{s}YAML{s}valid)'.format(s=log.utf('sep_v')))
        for _, subprefix, f in setup_files:
            token_script = token_load = token_yaml = log.utf('fail')
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
            log.print_item(' {}{}{}{}{} {}'.format(
                token_script,
                log.utf('sep_v'),
                token_load,
                log.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)
            ), with_bullet=False)

            if err:
                log.info("FAILED: {}".format(
                    base64.b64decode(err).decode('utf-8')))

    if yaml_files:
        log.print_section(
            "Analysis: pcvs.yml* (YAML{}Valid)".format(log.utf('sep_v')))
        for _, subprefix, f in yaml_files:
            with open(os.path.join(dir, subprefix, f), 'r') as fh:
                err, token_load, token_yaml = process_check_yaml_stream(
                    fh.read())
                if err:
                    errors.setdefault(err, 0)
                    errors[err] += 1

            log.print_item(' {}{}{} {}'.format(
                token_load,
                log.utf('sep_v'),
                token_yaml,
                os.path.join(dir, subprefix)), with_bullet=False)

            if err:
                log.info("FAILED: {}".format(
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
            log.warn("template already exist ! Skip.")
            return

        with open(out_file, 'w') as fh:
            yaml.dump(self._stream.to_dict(), fh)

class AutotoolsBuildSystem(BuildSystem):
    def fill(self):
        name = os.path.basename(self._root)
        self._stream[name].build.autotools.autogen = ('autogen.sh' in self._files)
        self._stream[name].build.files = os.path.join(self._root, 'configure')
        self._stream[name].build.autotools.params = ""

class CMakeBuildSystem(BuildSystem):
    def fill(self):
        name = os.path.basename(self._root)
        self._stream[name].build.cmake.vars = "CMAKE_BUILD_TYPE=Debug"
        self._stream[name].build.files = os.path.join(self._root, 'CMakeLists.txt')


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
            n = log.cl("Autotools", "yellow", bold=True)
            obj = AutotoolsBuildSystem(root, dirs, files)
        if 'CMakeLists.txt' in files:
            n = log.cl("CMake", "cyan", bold=True)
            obj = CMakeBuildSystem(root, dirs, files)
        if 'Makefile' in files:
            n = log.cl("Make", "red", bold=True)
            obj = MakefileBuildSystem(root, dirs, files)

        if obj is not None:
            dirs[:] = []
            log.print_item("{} [{}]".format(root, n))
            obj.fill()
            obj.generate_file(filename="pcvs.yml")
