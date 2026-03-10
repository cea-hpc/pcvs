import fileinput
import os
import pprint
import shutil
import subprocess
import time
from typing import Any

from ruamel.yaml import YAML

from pcvs import io
from pcvs import NAME_BUILD_CACHEDIR
from pcvs import NAME_BUILD_CONF_FN
from pcvs import NAME_BUILD_CONF_SH
from pcvs import NAME_BUILD_SCRATCH
from pcvs import NAME_BUILDFILE
from pcvs import NAME_BUILDIR
from pcvs import NAME_CONFIGDIR
from pcvs import testing
from pcvs.backend import bank as pvBank
from pcvs.backend import spack as pvSpack
from pcvs.backend.metaconfig import GlobalConfig
from pcvs.backend.metaconfig import MetaConfig
from pcvs.backend.session import Session
from pcvs.helpers import communications
from pcvs.helpers import criterion
from pcvs.helpers import utils
from pcvs.helpers.communications import GenericServer
from pcvs.helpers.exceptions import RunException
from pcvs.helpers.exceptions import ValidationException
from pcvs.io import Verbosity
from pcvs.orchestration import Orchestrator
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.plugins import Plugin
from pcvs.testing.tedesc import TEDescriptor
from pcvs.testing.test import Test
from pcvs.testing.testfile import TestFile


def print_progbar_walker(elt: tuple[str, str | None]) -> str | None:
    """
    Walker used to pretty-print progress bar element within Click.

    :param elt: the element to pretty-print, containing the label & subprefix
    :return: the formatted string
    """
    if elt is None:
        return None
    return "[" + elt[0] + "] " + (elt[1] if elt[1] else "")


def display_summary(the_session: Session) -> None:
    """
    Display a summary for this run, based on profile & CLI arguments.

    :param the_session: active session, for extra info to be displayed.
    """
    cfg = GlobalConfig.root["validation"]

    io.console.print_section("Global Information")
    io.console.print_item(
        "Date of execution: {}".format(GlobalConfig.root["validation"]["datetime"].strftime("%c"))
    )
    io.console.print_item("Run by: {} <{}>".format(cfg["author"]["name"], cfg["author"]["email"]))
    io.console.print_item("Active session ID: {}".format(the_session.id))
    io.console.print_item("Loaded profile: '{}'".format(cfg["pf_name"]))
    io.console.print_item("Build stored to: {}".format(cfg["output"]))
    io.console.print_item(
        "Criterion matrix size per job: {}".format(GlobalConfig.root.get_internal("comb_cnt"))
    )

    if "target_bank" in cfg:
        io.console.print_item("Bank Management: {}".format(cfg["target_bank"]))
    io.console.print_section("User directories:")
    width = max([0] + [len(i) for i in cfg["dirs"]])
    for k, v in cfg["dirs"].items():
        io.console.print_item("{:<{width}}: {:<{width}}".format(k.upper(), v, width=width))

    io.console.print_section("Globally loaded plugins:")
    GlobalConfig.root.get_internal("pColl").show_enabled_plugins()

    io.console.print_section("Orchestration infos")
    GlobalConfig.root.get_internal("orchestrator").print_infos()

    if cfg["simulated"] is True:
        io.console.print_box(
            "\n".join(
                [
                    "[red bold]DRY-RUN:[yellow] TEST EXECUTION IS [underline]EMULATED[/] <<<<",
                    "[yellow italic]>>>> Dry run enabled for setup checking purposes.",
                ]
            ),
            panel_options={
                "title": "WARNING",
            },
        )


def stop_pending_jobs(exc: Exception | None = None) -> None:
    """
    Called when PCVS is going to stop upon external request, stop the scheduler

    :param exc: exception to raise, defaults to None
    :raises exc: the exception to raise (this function is generally called when
        a exception is raised, this do some actions without capturing the exception)
    """
    orch = GlobalConfig.root.get_internal("orchestrator")
    if orch:
        orch.stop()
    if exc:
        raise exc


@io.capture_exception(Exception, stop_pending_jobs)
def process_main_workflow(the_session: Session) -> int:
    """
    Main run.py entry point, triggering a PCVS validation run.

    This function is called by session management and may be run within an
    active terminal or as a detached process.

    :param the_session: the session handler this run is connected to, defaults to None
    :return: the exit code
    """
    io.console.info("RUN: Session start")
    global_config: MetaConfig = GlobalConfig.root
    valcfg = global_config["validation"]

    valcfg["sid"] = the_session.id
    build_manager = BuildDirectoryManager(build_dir=valcfg["output"])
    global_config.set_internal("build_manager", build_manager)

    io.console.print_banner()
    io.console.print_header("Initialization")
    # prepare PCVS and third-party tools
    prepare()
    assert build_manager.config

    # get environment variables
    env_config = build_env_from_configuration(GlobalConfig.root)
    # export to process env
    os.environ.update(env_config)
    io.console.debug(
        f"Environment variables added for configuration:\n"
        f"{utils.str_dict_as_envvar(env_config)}"
    )

    if valcfg["reused_build"] is not None:
        io.console.print_section("Reusing previously generated inputs")
    else:
        io.console.print_section("Load Test Suites")
        start = time.time()
        if valcfg["dirs"]:
            tests = process_files()  # type: ignore
            for t in tests:
                GlobalConfig.root.get_internal("orchestrator").add_new_job(t)
        if valcfg["spack_recipe"]:
            process_spack()
        end = time.time()
        io.console.print_section("===> Processing done in {:<.3f} sec(s)".format(end - start))

    io.console.print_section("Resolving Test Dependencies")
    GlobalConfig.root.get_internal("orchestrator").compute_deps()

    io.console.print_header("Summary")
    display_summary(the_session)

    bank_token = valcfg["target_bank"]
    bank = None
    if bank_token is not None:
        io.console.print_section(f"===> Loading Bank: {bank_token}.")
        bank = pvBank.Bank(bank_token)
        GlobalConfig.root.set_internal("bank", bank)

    if valcfg["onlygen"]:
        io.console.warn(
            str(
                [
                    "====================================================",
                    "Tests won't be run. This program will now stop.",
                    "You may list runnable tests with `pcvs exec --list`",
                    "or execute one with `pcvs exec <testname>`",
                    "====================================================",
                ]
            )
        )
        return 0

    io.console.print_header("Execution")

    rc = global_config.get_internal("orchestrator").run(the_session)
    assert isinstance(rc, int)

    if io.console.verbosity >= Verbosity.DETAILED:
        io.console.print_header("Execution Summary")
        io.console.print_job_summary()

    io.console.print_header("Finalization")
    # post-actions to build the archive, post-process the webview...
    terminate()
    if bank is not None:
        io.console.print_item(f"Upload results to bank: '{bank_token}'")
        bank.save_new_run_from_instance(None, build_manager, msg=valcfg.get("message", None))
        bank.disconnect()
    buildfile = os.path.join(valcfg["output"], NAME_BUILDFILE)
    if utils.is_locked(buildfile):
        utils.unlock_file(buildfile)

    return rc


def check_defined_program_validity() -> None:
    """
    Ensure most programs defined in profiles & parameters are valid in the current environment.

    Only system-wide commands are assessed here (compiler, runtime, etc...) not
    test-wide, as some resource may not be available at the time.
    """
    assert GlobalConfig.root["machine"]
    if "job_manager" in GlobalConfig.root["machine"]:
        # exhaustive list of user-defined program to exist before starting:
        utils.check_valid_program(
            GlobalConfig.root["machine"]["job_manager"]["allocate"]["program"]
        )
        utils.check_valid_program(
            GlobalConfig.root["machine"]["job_manager"]["allocate"]["wrapper"]
        )
        utils.check_valid_program(GlobalConfig.root["machine"]["job_manager"]["remote"]["program"])
        utils.check_valid_program(GlobalConfig.root["machine"]["job_manager"]["remote"]["wrapper"])
        utils.check_valid_program(GlobalConfig.root["machine"]["job_manager"]["batch"]["program"])
        utils.check_valid_program(GlobalConfig.root["machine"]["job_manager"]["batch"]["wrapper"])

    for compiler in GlobalConfig.root["compiler"]["compilers"].values():
        compiler["valid"] = utils.check_valid_program(
            compiler["program"], fail=io.console.warning, raise_on_fail=False
        )
    utils.check_valid_program(GlobalConfig.root["runtime"]["program"])

    # TODO: need to handle package_manager commands to process below
    # maybe a dummy testfile should be used


def prepare() -> None:
    """
    Prepare the environment for a validation run.

    This function prepares the build dir, create trees...
    """
    io.console.print_section("Prepare environment")
    valcfg = GlobalConfig.root["validation"]
    build_man: BuildDirectoryManager = GlobalConfig.root.get_internal("build_manager")

    utils.start_autokill(valcfg["timeout"])

    io.console.print_item("Check whether build directory is valid")
    build_man.prepare(reuse=valcfg["reused_build"] is not None)

    per_file_max_sz = 0
    try:
        per_file_max_sz = int(valcfg["per_result_file_sz"])
    except (TypeError, ValueError):
        pass
    build_man.init_results(per_file_max_sz=per_file_max_sz)

    for label in valcfg["dirs"].keys():
        build_man.save_extras(os.path.join(NAME_BUILD_SCRATCH, label), directory=True, export=False)

    build_man.save_extras(NAME_BUILD_CACHEDIR, directory=True, export=False)
    valcfg["buildcache"] = os.path.join(build_man.prefix, NAME_BUILD_CACHEDIR)

    io.console.print_item("Ensure user-defined programs exist")
    check_defined_program_validity()

    io.console.print_item("Init & expand criterions")
    criterion.initialize_from_system()
    TEDescriptor.init_system_wide("n_node")

    if valcfg["enable_report"]:
        io.console.print_section("Connection to the Reporting Server")
        comman: GenericServer
        if valcfg["report_addr"] == "local":
            comman = communications.EmbeddedServer(valcfg["sid"])
            io.console.print_item("Running a local instance")
        else:
            comman = communications.RemoteServer(valcfg["sid"], valcfg["report_addr"])
            io.console.print_item("Listening on {}".format(comman.endpoint))
        GlobalConfig.root.set_internal("comman", comman)

    io.console.print_item("Init the global Orchestrator")
    GlobalConfig.root.set_internal("orchestrator", Orchestrator())

    io.console.print_item("Save Configurations into {}".format(valcfg["output"]))
    build_man.save_config(GlobalConfig.root)


def find_files_to_process(
    path_dict: dict[str, str],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """
    Lookup for test files to process, from the list of paths provided as parameter.

    The given `path_dict` is a dict, where keys are path labels given by the
    user, while values are the actual path. This function then returns a
    two-list tuple, one being files needing preprocessing (setup), the other
    being static configuration files (pcvs.yml)

    Each list element is a tuple:
         * origin label
         * subtree from this label leading to the actual file
         * file basename (either "pcvs.setup" or "pcvs.yml")

    :param path_dict: tree of paths to look for
    :return: a tuple with two lists
    """
    setup_files = []
    yaml_files = []
    io.console.debug(f"Looking for files in:\n{path_dict}")
    # discovery may take a while with some systems
    # iterate over user directories
    for label, path in path_dict.items():
        # for each, walk through the tree
        for root, dirs, list_files in os.walk(path):
            last_dir = os.path.basename(root)
            # if the current dir is a 'special' one, discard
            if last_dir in [NAME_CONFIGDIR, NAME_BUILDIR, "build_scripts"]:
                io.console.debug("skip {}".format(root))
                # set dirs to null, avoiding os.wal() to go further in that dir
                dirs[:] = []
                continue
            # otherwise, save the file
            for f in list_files:
                # [1:] to remove extra '/'
                subtree = os.path.relpath(root, path)
                if "pcvs.setup" == f:
                    setup_files.append((label, subtree, f))
                elif f in ("pcvs.yml", "pcvs.yml.in"):
                    yaml_files.append((label, subtree, f))
    return (setup_files, yaml_files)


@io.capture_exception(Exception, doexit=True)
def process_files() -> list[Test]:
    """
    Process the test-suite generation.

    It includes walking through user directories to find definitions AND
    generating the associated tests.

    :return: The list of tests to run.
    """
    io.console.print_item("Locate benchmarks from user directories")
    setup_files, yaml_files = find_files_to_process(GlobalConfig.root["validation"]["dirs"])

    io.console.debug(f"Found setup files: {pprint.pformat(setup_files)}")
    io.console.debug(f"Found static files: {pprint.pformat(yaml_files)}")

    prepare_runtime_env_file()

    tests: list[Test] = []
    io.console.print_item(f"Extract tests from dynamic definitions ({len(setup_files)} found)")
    tests += process_dyn_setup_scripts(setup_files)
    io.console.print_item(f"Extract tests from static definitions ({len(yaml_files)} found)")
    tests += process_static_yaml_files(yaml_files)
    return tests


def prepare_runtime_env_file() -> None:
    """Export run environment into a file for later import by runner script."""
    io.console.info("Building env from config.")
    env_config = build_env_from_configuration(GlobalConfig.root)

    with open(
        os.path.join(GlobalConfig.root["validation"]["output"], NAME_BUILD_CONF_SH),
        "w",
        encoding="utf-8",
    ) as fh:
        fh.write(utils.str_dict_as_envvar(env_config))
        fh.close()


def process_spack() -> None:
    """
    Build job to schedule from Spack recipes.
    """
    if not shutil.which("spack"):
        io.console.warn("Unable to parse Spack recipes without having Spack in $PATH")
        return
    io.console.print_item("Build test-bases from Spack recipes")
    label = "spack"
    path = "/spack"
    GlobalConfig.root["validation"]["dirs"][label] = path
    build_man = GlobalConfig.root.get_internal("build_manager")

    _, _, rbuild, _ = testing.test.generate_local_variables(label, "")
    build_man.save_extras(os.path.relpath(rbuild, build_man.prefix), dir=True, export=False)

    for spec in io.console.progress_iter(GlobalConfig.root["validation"]["spack_recipe"]):
        _, _, _, cbuild = testing.test.generate_local_variables(label, spec)
        build_man.save_extras(os.path.relpath(cbuild, build_man.prefix), dir=True, export=False)
        pvSpack.generate_from_variants(spec, label, spec)


def build_env_from_configuration(config: dict) -> dict:
    """
    Export configuration as env variables.

    Not all configuration are exported, only the one that may be used.
    compiler variables:
    - PCVS_CMP_CC=mpc_cc
    - PCVS_CMP_CC_ARGS=-O5
    - PCVS_CMP_CC_VAR_OPENMP=mpc_cc_omp
    - PCVS_CMP_CC_VAR_OPENMP_ARGS=-fopenmp

    criterions variables:
    - PCVS_CRIT_MPI='1 2 4'

    :param config: the current config
    :return: a dict of environment variables to export.
    """

    def to_str(item: Any) -> str:
        if item is None:
            return ""
        if isinstance(item, list):
            return " ".join(map(str, item))
        return str(item)

    env = {}
    for comp_name, comp in config["compiler"]["compilers"].items():
        env[f"PCVS_CMP_{comp_name}".upper()] = comp["program"]
        env[f"PCVS_CMP_{comp_name}_ARGS".upper()] = to_str(comp.get("args", ""))
        for var_name, variant in comp.get("variants", {}).items():
            env[f"PCVS_CMP_{comp_name}_VAR_{var_name}".upper()] = variant.get(
                "program", comp["program"]
            )
            env[f"PCVS_CMP_{comp_name}_VAR_{var_name}_ARGS".upper()] = to_str(
                variant.get("args", "")
            )
    for crit_name, criter in config["criterion"].items():
        env[f"PCVS_CRIT_{crit_name}".upper()] = to_str(criter["values"])
    compiler_env = testing.tedesc.extract_compilers_envs([])
    for e in compiler_env:
        k, v = e.split("=", 1)
        env[k] = v
    return env


def process_dyn_setup_scripts(setup_files: list[tuple[str, str, str]]) -> list[Test]:
    """
    Process all dynamic 'pcvs.yaml.setup' files and generate associated tests.

    This function executes pcvs.setup files after deploying the environment (to
    let these scripts access it). It leads to generate "pcvs.yml" files, then
    processed to construct tests.

    :param setup_files: list of tuples, each mapping a single pcvs.setup file
    :return: list of generated tests
    """
    io.console.info("Iteration over files")
    tests: list[Test] = []
    for label, prefix, fname in io.console.progress_iter(setup_files):
        tests += process_dyn_setup(label, prefix, fname)
    return tests


def process_static_yaml_files(yaml_files: list[tuple[str, str, str]]) -> list[Test]:
    """
    Process all static 'pcvs.yml' files and generate associated tests.

    :param yaml_files: list of tuples, each describing a single input file.
    :return: list of generated tests
    """
    io.console.info("Iteration over files")
    tests: list[Test] = []
    for label, prefix, fname in io.console.progress_iter(yaml_files):
        tests += process_static_yaml(label, prefix, fname)
    return tests


def process_dyn_setup(label: str, prefix: str, file_name: str) -> list[Test]:
    """
    Process one setup script and return it's test descriptor.

    :param label: The test file label.
    :param prefix: The test file prefix.
    :param file_name: The test file name.
    :raises SetupError: An error occurred when running the setup script.
    :raises NonZeroSetupScript: Script executed but exit code is not 0.
    :return: The list of tests to run.
    """
    io.console.info(f"Processing {prefix} dynamic script. ({label})")
    base_src, cur_src, base_build, cur_build = testing.test.generate_local_variables(label, prefix)
    os.makedirs(cur_build, exist_ok=True)
    f = os.path.join(cur_src, file_name)

    start_time = time.time()
    # prepre to exec pcvs.setup script
    # setup the env
    env = os.environ
    # env["PCVS_SRC"] = base_src
    env["pcvs_src"] = base_src
    # env["PCVS_BUILD"] = base_build
    env["pcvs_testbuild"] = base_build

    if not prefix:
        prefix = ""
    # Run the script
    try:
        fds = subprocess.Popen([f, prefix], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        fdout, fderr = fds.communicate()

        if fds.returncode != 0:
            raise RunException.NonZeroSetupScript(rc=fds.returncode, err=fderr, file=f)
        # should be enabled only in debug mode
        # flush the output to $BUILD/pcvs.yml
        # out_file = os.path.join(cur_build, 'pcvs.yml')
        # with open(out_file, 'w') as fh:
        # fh.write(fdout.decode('utf-8'))
    except Exception as err:
        raise ValidationException.SetupError(f) from err
    end_time = time.time()
    elapsed_time = end_time - start_time
    io.console.info(f"Subscript {prefix} done in {elapsed_time:.3f} seconds.")

    out = fdout.decode("utf-8")
    if not out:
        return []

    # Now create the file handler
    return process_yaml(file_path=f, build_path=cur_build, label=label, prefix=prefix, content=out)


def process_static_yaml(label: str, prefix: str, file_name: str) -> list[Test]:
    """Process one yaml file and return it's test descriptor."""
    _, cur_src, _, cur_build = testing.test.generate_local_variables(label, prefix)
    os.makedirs(cur_build, exist_ok=True)
    f = os.path.join(cur_src, file_name)

    return process_yaml(file_path=f, build_path=cur_build, label=label, prefix=prefix)


def process_yaml(
    file_path: str, build_path: str, label: str, prefix: str, content: str | None = None
) -> list[Test]:
    """
    Process one yaml and return it's test descriptor.

    :param file_path: The path to the test file.
    :param build_path: The path to the build directory.
    :param label: The test file label.
    :param prefix: The test file prefix.
    :param content: The yaml to use instead of the content of the yaml file, (use when generated by .setup script).
    :raises YamlError: An error occurred when loading the yaml file, invalid yaml structure of file.
    :return: The list of tests to run.
    """
    GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.TFILE_BEFORE)

    tests: list[Test] = []
    try:
        test_file = TestFile(file_in=file_path, path_out=build_path, label=label, prefix=prefix)

        if content is None:
            test_file.load_from_file()
        else:
            test_file.load_from_str(content)
            test_file.save_yaml()

        test_file.process()
        tests = test_file.tests
        test_file.flush_sh_file()
        io.console.info(f"Adding {test_file.nb_tests} tests from {file_path}.")
    except Exception as e:
        raise ValidationException.YamlError(file_path, str(test_file.raw_yaml)) from e
        # io.console.error(
        #    f"In file: {file_path}\nFailed to parse the following invalid yaml:\n{test_file.raw_yaml}"
        # )
        # raise e

    GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.TFILE_AFTER)
    return tests


def anonymize_archive() -> None:
    """
    Erase from results any undesired output from the generated archive.

    This process is disabled by default as it may increase significantly the
    validation process on large test bases.

    .. note::
        It does not alter results in-place, only the generated archive. To
        preserve the anonymization, only the archive must be exported/shared,
        not the actual build directory.
    """
    outdir = GlobalConfig.root["validation"]["output"]
    for root, _, files in os.walk(outdir):
        for f in files:
            if not f.endswith((".xml", ".json", ".yml", ".txt", ".md", ".html")):
                continue
            with fileinput.FileInput(os.path.join(root, f), inplace=True, backup=".raw") as fh:
                for line in fh:
                    # TODO: add more patterns (user-defined ? )
                    print(
                        line.replace(outdir, "${PCVS_RUN_DIRECTORY}")
                        .replace(os.environ["HOME"], "${HOME}")
                        .replace(os.environ["USER"], "${USER}"),
                        end="",
                    )


def terminate() -> None:
    """
    Finalize a validation run.

    This include generating & anonymizing (if needed) the archive.
    """
    GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.END_BEFORE)

    build_man = GlobalConfig.root.get_internal("build_manager")
    outdir = GlobalConfig.root["validation"]["output"]

    io.console.print_section("Prepare results")
    io.console.move_debug_file(outdir)
    archive_path = build_man.create_archive()
    io.console.print_item("Archive: {}".format(archive_path))

    # if GlobalConfig.root['validation']['anonymize']:
    #    io.console.print_item("Anonymize data")
    #    anonymize_archive()

    comman = GlobalConfig.root.get_internal("comman")
    if comman:
        io.console.print_item("Close connection to Reporting Server")
        comman.close_connection()
    GlobalConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.END_AFTER)
    build_man.finalize()


def dup_another_build(build_dir: str, outdir: str) -> MetaConfig:
    """
    Clone another build directory to start this validation upon it.

    It allows to save test-generation time if the validation is re-run under the
    exact same terms (identical configuration & tests).

    :param build_dir: the build directory to copy resource from
    :param outdir: where data will be copied to.
    :return: the whole configuration loaded from the dup'd build directory
    """
    global_config = None

    # First, load the whole config
    with open(os.path.join(build_dir, NAME_BUILD_CONF_FN), "r") as fh:
        d = YAML(typ="safe").load(fh)
        global_config = MetaConfig(d)

    # first, clear fields overridden by current run
    global_config["validation"]["output"] = outdir
    global_config["validation"]["reused_build"] = build_dir
    global_config["validation"]["buildcache"] = os.path.join(outdir, NAME_BUILD_CACHEDIR)

    # second, copy any xml/sh files to be reused
    for root, _, files in os.walk(os.path.join(build_dir, "test_suite")):
        for f in files:
            if f in ("dbg-pcvs.yml", "list_of_tests.sh"):
                src = os.path.join(root, f)
                dest = os.path.join(outdir, os.path.relpath(src, start=os.path.abspath(build_dir)))

                utils.copy_file(src, dest)

    # other files
    for f in NAME_BUILD_CONF_SH:
        src = os.path.join(build_dir, f)
        dest = os.path.join(outdir, os.path.relpath(src, start=os.path.abspath(build_dir)))
        if not os.path.isfile(src):
            continue

        utils.copy_file(src, dest)

    return global_config
