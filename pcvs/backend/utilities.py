import base64
import json
import os
import subprocess
import tempfile

from ruamel.yaml import YAML, YAMLError

from pcvs import NAME_BUILDFILE, NAME_BUILDIR, io
from pcvs.testing.testfile import TestFile
from pcvs.backend import config, profile, run
from pcvs.helpers import system, utils
from pcvs.helpers.exceptions import ValidationException
from pcvs.helpers.system import MetaDict
from pcvs.orchestration.publishers import BuildDirectoryManager


def locate_scriptpaths(output=None):
    """Path lookup to find all 'list_of_tests' script within a given prefix.

    :param output: prefix to walk through, defaults to current directory
    :type output: str, optional
    :return: the list of scripts found in prefix
    :rtype: List[str]
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
    :return: the associated path with testname
    :rtype: str
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


def get_logged_output(prefix, testname):
    if prefix is None:
        prefix = os.getcwd()
    buildir = utils.find_buildir_from_prefix(prefix)
    s = ""
    if buildir:
        man = BuildDirectoryManager(build_dir=buildir)
        man.init_results()
        for test in man.results.retrieve_tests_by_name(name=testname):
            s += "\n##### TEST OUTPUT #####\n### Testname: {}\n{}\n".format(
                test.name, test.get_raw_output(encoding='utf-8'))
        man.finalize()
    if not s:
        s = "No test named '{}' found here.".format(testname)

    return s


def process_check_configs(conversion=True):
    """Analyse available configurations to ensure their correctness relatively
    to their respective schemes.

    :return: caught errors, as a dict, where the keys is the errmsg base64
    :rtype: dict"""
    errors = dict()
    t = io.console.create_table("Configurations", ["Valid", "ID"])

    for kind in config.CONFIG_BLOCKS:
        for scope in utils.storage_order():
            for blob in config.list_blocks(kind, scope):
                token = io.console.utf('fail')
                err_msg = ""
                obj = config.ConfigurationBlock(kind, blob[0], scope)
                obj.load_from_disk()

                try:
                    obj.check(allow_legacy=conversion)
                    token = io.console.utf('succ')
                except ValidationException.FormatError as e:
                    err_msg = base64.b64encode(str(e.dbg).encode('utf-8'))
                    errors.setdefault(err_msg, 0)
                    errors[err_msg] += 1
                    io.console.debug(str(e))

                t.add_row(token, obj.full_name)
    io.console.print(t)
    return errors


def process_check_profiles(conversion=True):
    """Analyse availables profiles and check their correctness relatively to the
    base scheme.

    :return: list of caught errors as a dict, where keys are error msg base64
    :rtype: dict"""
    t = io.console.create_table("Available Profile", ["valid", "ID"])
    errors = dict()

    for scope in utils.storage_order():
        for blob in profile.list_profiles(scope):
            token = io.console.utf('fail')
            obj = profile.Profile(blob[0], scope)
            obj.load_from_disk()
            try:
                obj.check(allow_legacy=conversion)
                token = io.console.utf('succ')
            except ValidationException.FormatError as e:
                err_msg = base64.b64encode(str(e.dbg).encode('utf-8'))
                errors.setdefault(err_msg, 0)
                errors[err_msg] += 1
                io.console.debug(str(e))

            t.add_row(token, obj.full_name)
    io.console.print(t)
    return errors


def process_check_setup_file(root, prefix, run_configuration):
    """Check if a given pcvs.setup could be parsed if used in a regular process.

    :param filename: the pcvs.setup filepath
    :type filename: str
    :param prefix: the subtree the setup is extract from (used as argument)
    :type prefix: str
    :return: a tuple (err msg, icon to print, parsed data)
    :rtype: tuple
    """
    err_msg = None
    data = None
    env = os.environ
    env.update(run_configuration)

    try:
        tdir = tempfile.mkdtemp()
        with utils.cwd(tdir):
            env['pcvs_src'] = root
            env['pcvs_testbuild'] = tdir
            
            if not os.path.isdir(os.path.join(tdir, prefix)):
                os.makedirs(os.path.join(tdir, prefix))
            if not prefix:
                prefix = ''
            proc = subprocess.Popen(
                [os.path.join(root, prefix, "pcvs.setup"), prefix], env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            fdout, fderr = proc.communicate()

            if proc.returncode != 0:
                if not fderr:
                    fderr = "Non-zero status (no stderr): {}".format(
                        proc.returncode).encode('utf-8')
                err_msg = base64.b64encode(fderr)
            else:
                data = fdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        err_msg = base64.b64encode(str(e.stderr).encode('utf-8'))

    return (err_msg, data)

def __set_token(token, nset=None) -> str:
    """Manage display token (job display) depending on given condition.

    if the condition is a success, insert the UTF 'succ' code, 'fail' otherwise.
    A custom str can be provided if the condition is neither a success or a
    failure (=None was given).

    :param token: the condition
    :type token: bool
    :param nset: default pattern to insert
    :type nset: str, optional
    :return: the pretty-printable token
    :rtype: str
    """
    if not nset:
        nset = io.console.utf("none")
    if token is None:
        return "[yellow bold]{}[/]".format(nset)
    elif token:
        return "[green bold]{}[/]".format(io.console.utf("succ"))
    else:
        return "[red bold]{}[/]".format(io.console.utf("fail"))


def process_check_directory(dir, pf_name="default", conversion=True):
    """Analyze a directory to ensure defined test files are valid.

    :param dir: the directory to process.
    :type dir: str
    :return: a dict of caught errors
    :rtype: dict
    """
    errors = dict()
    total_nodes = 0
    pf = profile.Profile(pf_name)
    if not pf.is_found():
        pf.load_template()
    else:
        pf.load_from_disk()
        pf.check(allow_legacy=conversion)
    system.MetaConfig.root = system.MetaConfig()
    system.MetaConfig.root.bootstrap_from_profile(pf.dump())
    system.MetaConfig.root.validation.output = "/tmp"
    buildenv = run.build_env_from_configuration(pf.dump())
    setup_files, yaml_files = run.find_files_to_process(
        {os.path.basename(dir): dir})

    from rich.table import Table
    table = Table(title="Results", expand=True, row_styles=["dim", ""])
    table.add_column("Runnable Script", justify="center", max_width=5)
    table.add_column("Valid", justify="center", max_width=5)
    table.add_column("Node count", justify="center", max_width=5)
    table.add_column("File Path", justify="left")
    # with io.console.pager():
    # with Live(table, refresh_per_second=4):
    for _, subprefix, f in io.console.progress_iter([*setup_files, *yaml_files]):
        setup_ok = __set_token(None)
        yaml_ok = __set_token(None)
        nb_nodes = __set_token(None, "----")
        data = ""
        err = None

        if subprefix is None:
            subprefix = ""

        if f.endswith("pcvs.setup"):
            err, data = process_check_setup_file(
                dir, subprefix, buildenv)
            setup_ok = __set_token(err is None)
        else:
            with open(os.path.join(dir, subprefix, f), 'r') as fh:
                data = fh.read()

        if not err:
            converted = None
            dflt = None
            err = None
            try:
                cur = TestFile(file_in="", path_out="", label="", prefix=subprefix)
                cur.load_from_str(data)
                converted = not(cur.validate(allow_conversion=conversion))
                nb_nodes = cur.nb_descs
                total_nodes += nb_nodes
                success=True

            except YAMLError as e:
                err = base64.b64encode(str(e).encode('utf-8'))
                success=False
            except ValidationException.FormatError as e:
                err = base64.b64encode(str(e).encode('utf-8'))
                success=False
                
            if converted is True:
                # yaml VALID but old syntax
                # --> yellow
                success=None
                dflt = "{} {}".format(io.console.utf('succ'), io.console.utf('copy'))
            yaml_ok = __set_token(success, nset=dflt)
            

        table.add_row(
            setup_ok,
            yaml_ok,
            "{:>4}" .format(nb_nodes),
            "./" if not subprefix else subprefix)

        if err:
            io.console.info("FAILED: {}".format(
                base64.b64decode(err).decode('utf-8')))
            errors.setdefault(err, 0)
            errors[err] += 1
    io.console.print(table)
    io.console.print_item("Total node count: {}".format(total_nodes))
    return errors


class BuildSystem:
    """Manage a generic build system discovery service.

    :ivar _root: the root directory the discovery service is attached to.
    :type _root: str
    :ivar _dirs: list of directory found in _root.
    :type _dirs: List[str]
    :ivar _files: list of files found in _root
    :type _files: List[str]
    :ivar _stream: the resulted dict, representing targeted YAML architecture
    :type _stream: dict"""

    def __init__(self, root, dirs=None, files=None):
        """Constructor method.

        :param root: root dir where discovery service is applied
        :type root: str
        :param dirs: list of dirs, defaults to None
        :type dirs: str, optional
        :param files: list of files, defaults to None
        :type files: str, optional
        """
        self._root = root
        self._dirs = dirs
        self._files = files
        self._stream = MetaDict()

    def fill(self):
        """This function should be overriden by overriden classes.

        Nothing to do, by default.
        """
        assert (False)

    def generate_file(self, filename="pcvs.yml", force=False):
        """Build the YAML test file, based on path introspection and build
        model.

        :param filename: test file suffix
        :type filename: str
        :param force: erase target file if exist.
        :type force: bool
        """
        out_file = os.path.join(self._root, filename)
        if os.path.isfile(out_file) and not force:
            io.console.warn(" --> skipped, already exist;")
            return

        with open(out_file, 'w') as fh:
            YAML(typ='safe').dump(self._stream.to_dict(), fh)


class AutotoolsBuildSystem(BuildSystem):
    """Derived BuildSystem targeting Autotools projects."""

    def fill(self):
        """Populate the dict relatively to the build system to build the proper
        YAML representation."""
        name = os.path.basename(self._root)
        self._stream[name].build.autotools.autogen = (
            'autogen.sh' in self._files)
        self._stream[name].build.files = os.path.join(self._root, 'configure')
        self._stream[name].build.autotools.params = ""


class CMakeBuildSystem(BuildSystem):
    """Derived BuildSystem targeting CMake projects."""

    def fill(self):
        """Populate the dict relatively to the build system to build the proper
        YAML representation."""
        name = os.path.basename(self._root)
        self._stream[name].build.cmake.vars = "CMAKE_BUILD_TYPE=Debug"
        self._stream[name].build.files = os.path.join(
            self._root, 'CMakeLists.txt')


class MakefileBuildSystem(BuildSystem):
    """Derived BuildSystem targeting Makefile-based projects."""

    def fill(self):
        """Populate the dict relatively to the build system to build the proper
        YAML representation."""
        name = os.path.basename(self._root)
        self._stream[name].build.make.target = ''
        self._stream[name].build.files = os.path.join(self._root, 'Makefile')


def process_discover_directory(path, override=False, force=False):
    """Path discovery to detect & intialize build systems found.

    :param path: the root path to start with
    :type path: str
    :param override: True if test files should be generated, default to False
    :type override: bool
    :param force: True if test files should be replaced if exist, defaut to False
    :type force: bool
    """
    for root, dirs, files in os.walk(path):
        obj = None
        if 'configure' in files:
            n = "[yello bold]Autotools[/]"
            obj = AutotoolsBuildSystem(root, dirs, files)
        if 'CMakeLists.txt' in files:
            n = "[cyan bold]CMake[/]"
            obj = CMakeBuildSystem(root, dirs, files)
        if 'Makefile' in files:
            n = "[red bold]Make[/]"
            obj = MakefileBuildSystem(root, dirs, files)

        if obj is not None:
            dirs[:] = []
            io.console.print_item("{} [{}]".format(root, n))
            obj.fill()
            if override:
                obj.generate_file(filename="pcvs.yml", force=force)
