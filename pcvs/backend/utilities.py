import os
from abc import abstractmethod
from typing import Any

from click import BadArgumentUsage
from rich.table import Column
from ruamel.yaml import YAML

from pcvs import io
from pcvs.backend import run
from pcvs.backend.config import Config
from pcvs.backend.configfile import ConfigFile
from pcvs.backend.configfile import Profile
from pcvs.backend.metaconfig import GlobalConfig
from pcvs.helpers import criterion
from pcvs.helpers import utils
from pcvs.helpers.exceptions import PCVSException
from pcvs.helpers.exceptions import ValidationException
from pcvs.helpers.storage import ConfigDesc
from pcvs.helpers.storage import ConfigKind
from pcvs.helpers.storage import ConfigLocator
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.testing.tedesc import TEDescriptor


def locate_scriptpaths(output: str | None = None) -> list[str]:
    """
    Path lookup to find all 'list_of_tests' script within a given prefix.

    :param output: prefix to walk through, defaults to current directory
    :return: the list of scripts found in prefix
    """
    if output is None:
        output = os.getcwd()
    scripts = []
    for root, _, files in os.walk(output):
        for f in files:
            if f == "list_of_tests.sh":
                scripts.append(os.path.join(root, f))
    return scripts


def compute_scriptpath_from_testname(testname: str, output: str | None = None) -> str:
    """
    Locate the proper 'list_of_tests.sh' according to a fully-qualified test name.

    :param testname: test name belonging to the script
    :param output: prefix to walk through, defaults to current directory
    :return: the associated path with testname
    """
    if output is None:
        output = os.getcwd()

    buildir = utils.find_buildir_from_prefix(output)
    prefix = os.path.dirname(testname)
    return os.path.join(buildir, "test_suite", prefix, "list_of_tests.sh")


def get_logged_output(prefix: str, testname: str) -> str:
    """
    Get job output from the given archive/build path.

    :param prefix: the archive or directory to scan from
    :param testname: the full test name
    :return: the raw output
    """
    if prefix is None:
        prefix = os.getcwd()
    buildir = utils.find_buildir_from_prefix(prefix)
    s = ""
    if buildir:
        man = BuildDirectoryManager(build_dir=buildir)
        man.init_results()
        for test in man.results.retrieve_tests_by_name(name=testname):
            output = test.output
            s += output
        man.finalize()
    if not s:
        s = "No test named '{}' found here.".format(testname)

    return s


def process_check_configs() -> dict[str, int]:
    """Analyse available configurations.

    To ensure their correctness relatively to their respective schemes.

    :return: caught errors, as a dict, where the keys is the errmsg base64
    """
    errors: dict[str, int] = {}
    t = io.console.create_table("Configurations", [Column("Valid"), Column("ID")])

    cds: list[ConfigDesc] = ConfigLocator().list_all_configs()
    for cd in cds:
        if cd.kind == ConfigKind.PLUGIN:
            continue
        token = io.console.utf("fail")
        try:
            ConfigFile(cd)
            token = io.console.utf("succ")
        except ValidationException.FormatError as e:
            err_msg = str(e)
            errors.setdefault(err_msg, 0)
            errors[err_msg] += 1
            io.console.debug(str(e))

        t.add_row(token, cd.full_name)
    io.console.print_rich(t)
    return errors


def process_check_profiles() -> dict[str, int]:
    """
    Analyse availables profiles and check their correctness.

    Relatively to the base scheme.

    :return: list of caught errors as a dict, where keys are error msg base64
    """
    t = io.console.create_table("Available Profiles", [Column("Valid"), Column("ID")])
    errors: dict[str, int] = {}

    cds: list[ConfigDesc] = ConfigLocator().list_configs(ConfigKind.PROFILE)
    for cd in cds:
        token = io.console.utf("fail")
        try:
            Profile(cd)
            token = io.console.utf("succ")
        except BadArgumentUsage as e:
            err_msg = e.message
            errors.setdefault(err_msg, 0)
            errors[err_msg] += 1
            io.console.debug(e.message)
        except ValidationException.FormatError as e:
            err_msg = str(e)
            errors.setdefault(err_msg, 0)
            errors[err_msg] += 1
            io.console.debug(str(e))

        t.add_row(token, cd.full_name)
    io.console.print_rich(t)
    return errors


def process_check_directory(directory: str, pf_name: str = "default.yml") -> dict[str, int]:
    """
    Analyze a directory to ensure defined test files are valid.

    :param directory: the directory to process.
    :param pf_name: profile name to be loaded, defaults to "default"
    :return: a dict of caught errors
    """
    errors: dict[str, int] = {}
    cd: ConfigDesc = ConfigLocator().parse_full_raise(
        pf_name, ConfigKind.PROFILE, should_exist=True
    )
    pf = Profile(cd)

    GlobalConfig.root.bootstrap_validation(Config())
    GlobalConfig.root.bootstrap_from_profile(pf)
    GlobalConfig.root["validation"]["output"] = "/tmp"
    GlobalConfig.root["validation"]["dirs"] = {os.path.basename(directory): directory}

    build_manager = BuildDirectoryManager(build_dir=GlobalConfig.root["validation"]["output"])
    GlobalConfig.root.set_internal("build_manager", build_manager)

    # run prepare section:
    run.check_defined_program_validity()
    criterion.initialize_from_system()
    TEDescriptor.init_system_wide("n_node")
    # GlobalConfig.root.set_internal("orchestrator", Orchestrator())

    # get environment variables
    env_config = run.build_env_from_configuration(GlobalConfig.root)
    # export to process env
    os.environ.update(env_config)
    # get files to validate
    setup_files, yaml_files = run.find_files_to_process({os.path.basename(directory): directory})

    from rich.table import Table

    table = Table(title="Results", expand=True)
    table.add_column("Runnable Script", justify="center", max_width=5)
    table.add_column("Valid YAML", justify="center", max_width=5)
    table.add_column("File Path", justify="left")

    token_ok = f"[green bold]{io.console.utf('succ')}[/]"
    token_bad = f"[red bold]{io.console.utf('fail')}[/]"
    token_unknown = f"[yellow bold]{io.console.utf('none')}[/]"

    for label, subtree, file in io.console.progress_iter([*setup_files, *yaml_files]):
        is_setup = (label, subtree, file) in setup_files
        setup_ok = token_ok if is_setup else token_unknown
        yaml_ok = token_ok
        err: PCVSException | None = None

        if subtree is None:
            subtree = ""

        try:
            if is_setup:
                run.process_dyn_setup(label, subtree, file)
            else:
                run.process_static_yaml(label, subtree, file)
        except ValidationException.YamlError as val_err:
            err = val_err
            yaml_ok = token_bad
        except ValidationException.SetupError as setup_err:
            err = setup_err
            setup_ok = token_bad
            yaml_ok = token_unknown

        table.add_row(setup_ok, yaml_ok, "." if not subtree else subtree)
        if err:
            io.console.error(str(err))
            errors.setdefault(str(err), 0)
            errors[str(err)] += 1

    io.console.print_rich(table)
    return errors


class BuildSystem:
    """
    Manage a generic build system discovery service.

    :ivar _root: the root directory the discovery service is attached to.
    :vartype _root: :py:obj:`str`
    :ivar _dirs: list of directory found in _root.
    :vartype _dirs: :py:obj:`list[str]`
    :ivar _files: list of files found in _root
    :vartype _files: :py:obj:`list[str]`
    :ivar _stream: the resulted dict, representing targeted YAML architecture
    :vartype _stream: :py:obj:`dict`
    """

    def __init__(self, root: str, dirs: list[str] | None = None, files: list[str] | None = None):
        """
        Constructor method.

        :param root: root dir where discovery service is applied
        :param dirs: list of dirs, defaults to None
        :param files: list of files, defaults to None
        """
        self._root = root
        self._dirs = dirs
        self._files = files
        self._stream: dict[str, Any] = {}

    @abstractmethod
    def fill(self) -> None:
        """
        This function should be overridden by overridden classes.

        Nothing to do, by default.
        """

    def generate_file(self, filename: str = "pcvs.yml", force: bool = False) -> None:
        """Build the YAML test file, based on path introspection and build
        model.

        :param filename: test file suffix
        :param force: erase target file if exist.
        """
        out_file = os.path.join(self._root, filename)
        if os.path.isfile(out_file) and not force:
            io.console.warn(" --> skipped, already exist;")
            return

        with open(out_file, "w") as fh:
            YAML(typ="safe").dump(self._stream, fh)


class AutotoolsBuildSystem(BuildSystem):
    """Derived BuildSystem targeting Autotools projects."""

    def fill(self) -> None:
        """Populate the dict relatively to the build system to build the proper YAML representation."""
        name = os.path.basename(self._root)
        self._stream.setdefault(name, {}).setdefault("build", {}).setdefault("autotools", {})
        self._stream[name]["build"]["autotools"]["autogen"] = (
            ("autogen.sh" in self._files) if self._files is not None else False
        )
        self._stream[name]["build"]["files"] = os.path.join(self._root, "configure")
        self._stream[name]["build"]["autotools"]["params"] = ""


class CMakeBuildSystem(BuildSystem):
    """Derived BuildSystem targeting CMake projects."""

    def fill(self) -> None:
        """Populate the dict relatively to the build system to build the proper YAML representation."""
        name = os.path.basename(self._root)
        self._stream.setdefault(name, {}).setdefault("build", {}).setdefault("cmake", {})
        self._stream[name]["build"]["cmake"]["vars"] = "CMAKE_BUILD_TYPE=Debug"
        self._stream[name]["build"]["files"] = os.path.join(self._root, "CMakeLists.txt")


class MakefileBuildSystem(BuildSystem):
    """Derived BuildSystem targeting Makefile-based projects."""

    def fill(self) -> None:
        """Populate the dict relatively to the build system to build the proper YAML representation."""
        name = os.path.basename(self._root)
        self._stream.setdefault(name, {}).setdefault("build", {}).setdefault("make", {})
        self._stream[name]["build"]["make"]["target"] = ""
        self._stream[name]["build"]["files"] = os.path.join(self._root, "Makefile")


def process_discover_directory(path: str, override: bool = False, force: bool = False) -> None:
    """
    Path discovery to detect & initialize build systems found.

    :param path: the root path to start with
    :param override: True if test files should be generated, default to False
    :param force: True if test files should be replaced if exist, default to False
    """
    for root, dirs, files in os.walk(path):
        obj: BuildSystem | None = None
        n = None
        if "configure" in files:
            n = "[yellow bold]Autotools[/]"
            obj = AutotoolsBuildSystem(root, dirs, files)
        if "CMakeLists.txt" in files:
            n = "[cyan bold]CMake[/]"
            obj = CMakeBuildSystem(root, dirs, files)
        if "Makefile" in files:
            n = "[red bold]Make[/]"
            obj = MakefileBuildSystem(root, dirs, files)

        if obj is not None:
            dirs[:] = []
            io.console.print_item(f"{root} [{n}]")
            obj.fill()
            if override:
                obj.generate_file(filename="pcvs.yml", force=force)
