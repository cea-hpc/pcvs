import fileinput
import os
import pprint
import shutil
import signal
import subprocess
import time
from subprocess import CalledProcessError

from ruamel.yaml import YAML

from pcvs import (NAME_BUILD_CONF_FN, NAME_BUILD_CACHEDIR, NAME_BUILD_SCRATCH,
                  NAME_BUILDFILE, NAME_BUILDIR, NAME_BUILD_CONF_SH, NAME_SRCDIR,
                  io, testing)
from pcvs.backend import bank as pvBank
from pcvs.backend import spack as pvSpack
from pcvs.helpers import communications, criterion, utils
from pcvs.helpers.exceptions import TestException, RunException
from pcvs.helpers.system import MetaConfig, MetaDict
from pcvs.orchestration import Orchestrator
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.plugins import Plugin
from pcvs.testing.tedesc import TEDescriptor
from pcvs.testing.testfile import TestFile


def print_progbar_walker(elt):
    """Walker used to pretty-print progress bar element within Click.

    :param elt: the element to pretty-print, containing the label & subprefix
    :type elt: tuple
    :return: the formatted string
    :rtype: str
    """
    if elt is None:
        return None
    return "["+elt[0]+"] " + (elt[1] if elt[1] else "")


def display_summary(the_session):
    """Display a summary for this run, based on profile & CLI arguments."""
    cfg = MetaConfig.root.validation

    io.console.print_section("Global Information")
    io.console.print_item("Date of execution: {}".format(
        MetaConfig.root.validation.datetime.strftime("%c")))
    io.console.print_item("Run by: {} <{}>".format(
        cfg.author.name, cfg.author.email))
    io.console.print_item("Active session ID: {}".format(the_session.id))
    io.console.print_item("Loaded profile: '{}'".format(cfg.pf_name))
    io.console.print_item("Build stored to: {}".format(cfg.output))
    io.console.print_item("Criterion matrix size per job: {}".format(
        MetaConfig.root.get_internal("comb_cnt")
    ))

    if cfg.target_bank:
        io.console.print_item("Bank Management: {}".format(cfg.target_bank))
    io.console.print_section("User directories:")
    width = max([0] + [len(i) for i in cfg.dirs])
    for k, v in cfg.dirs.items():
        io.console.print_item("{:<{width}}: {:<{width}}".format(
            k.upper(),
            v,
            width=width))

    io.console.print_section("Globally loaded plugins:")
    MetaConfig.root.get_internal("pColl").show_enabled_plugins()

    io.console.print_section("Orchestration infos")
    MetaConfig.root.get_internal("orchestrator").print_infos()

    if cfg.simulated is True:
        io.console.print_box("\n".join([
            "[red bold]DRY-RUN:[yellow] TEST EXECUTION IS [underline]EMULATED[/] <<<<",
            "[yellow italic]>>>> Dry run enabled for setup checking purposes."]), title="WARNING")


def stop_pending_jobs(exc=None):
    orch = MetaConfig.root.get_internal('orchestrator')
    if orch:
        orch.stop()
    if exc:
        raise exc


@io.capture_exception(Exception, stop_pending_jobs)
def process_main_workflow(the_session=None):
    """Main run.py entry point, triggering a PCVS validation run.

    This function is called by session management and may be run within an
    active terminal or as a detached process.

    :param the_session: the session handler this run is connected to, defaults to None
    :type the_session: :class:`Session`, optional
    """
    io.console.info("RUN: Session start")
    global_config = MetaConfig.root
    valcfg = global_config.validation
    rc = 0

    valcfg.sid = the_session.id
    build_manager = BuildDirectoryManager(build_dir=valcfg.output)
    MetaConfig.root.set_internal('build_manager', build_manager)

    io.console.print_banner()
    io.console.print_header("Initialization")
    # prepare PCVS and third-party tools
    prepare()
    assert(build_manager.config)

    if valcfg.reused_build is not None:
        io.console.print_section("Reusing previously generated inputs")
    else:
        io.console.print_section("Load Test Suites")
        start = time.time()
        if MetaConfig.root.validation.dirs:
            process_files()
        if MetaConfig.root.validation.spack_recipe:
            process_spack()
        end = time.time()
        io.console.print_section(
            "===> Processing done in {:<.3f} sec(s)".format(end-start))

    io.console.print_header("Summary")
    display_summary(the_session)

    if valcfg.onlygen:
        io.console.warn(
            ["====================================================",
             "Tests won't be run. This program will now stop.",
             "You may list runnable tests with `pcvs exec --list`",
             "or execute one with `pcvs exec <testname>`",
             "===================================================="
             ])
        return 0

    io.console.print_header("Execution")
    run_rc = MetaConfig.root.get_internal('orchestrator').run(the_session)
    rc += run_rc if isinstance(run_rc, int) else 1

    io.console.print_header("Finalization")
    # post-actions to build the archive, post-process the webview...
    terminate()

    bank_token = valcfg.target_bank
    if bank_token is not None:
        bank = pvBank.Bank(token=bank_token)
        pref_proj = bank.default_project
        if bank.exists():
            io.console.print_item("Upload results to bank: '{}{}'".format(
                bank.name.upper(),
                " (@{})".format(pref_proj) if pref_proj else ""
            ))

            bank.save_new_run_from_instance(None, build_manager, msg=valcfg.get('message', None))
            #bank.save_from_buildir(
            #    None,
            #    os.path.join(valcfg.output)
            #)

    buildfile = os.path.join(valcfg.output, NAME_BUILDFILE)
    if utils.is_locked(buildfile):
        utils.unlock_file(buildfile)

    return rc


def __check_defined_program_validity():
    """Ensure most programs defined in profiles & parameters are valid in the
    current environment.

    Only system-wide commands are assessed here (compiler, runtime, etc...) not
    test-wide, as some resource may not be available at the time.
    """
    # exhaustive list of user-defined program to exist before starting:
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.allocate.program)
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.allocate.wrapper)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.remote.program)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.remote.wrapper)
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.batch.program)
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.batch.wrapper)
    return
    # TODO: need to handle package_manager commands to process below
    # maybe a dummy testfile should be used
    utils.check_valid_program(MetaConfig.root.compiler.cc.program)
    utils.check_valid_program(MetaConfig.root.compiler.cxx.program)
    utils.check_valid_program(MetaConfig.root.compiler.fc.program)
    utils.check_valid_program(MetaConfig.root.compiler.f77.program)
    utils.check_valid_program(MetaConfig.root.compiler.f90.program)
    utils.check_valid_program(MetaConfig.root.runtime.program)


def prepare():
    """Prepare the environment for a validation run.

    This function prepares the build dir, create trees...
    """
    io.console.print_section("Prepare environment")
    valcfg = MetaConfig.root.validation
    build_man = MetaConfig.root.get_internal('build_manager')

    utils.start_autokill(valcfg.timeout)

    io.console.print_item("Check whether build directory is valid")
    build_man.prepare(reuse=valcfg.reused_build)

    per_file_max_sz = 0
    try:
        per_file_max_sz = int(valcfg.per_result_file_sz)
    except:
        pass
    build_man.init_results(per_file_max_sz=per_file_max_sz)

    for label in valcfg.dirs.keys():
        build_man.save_extras(os.path.join(NAME_BUILD_SCRATCH, label),
                              dir=True,
                              export=False)

    build_man.save_extras(NAME_BUILD_CACHEDIR, dir=True, export=False)
    valcfg.buildcache = os.path.join(build_man.prefix, NAME_BUILD_CACHEDIR)
    
    io.console.print_item("Ensure user-defined programs exist")
    __check_defined_program_validity()

    io.console.print_item("Init & expand criterions")
    criterion.initialize_from_system()
    # Pick on criterion used as 'resources' by JCHRONOSS
    # this is set by the run configuration
    # TODO: replace resource here by the one read from config
    TEDescriptor.init_system_wide('n_node')

    if valcfg.enable_report:
        io.console.print_section("Connection to the Reporting Server")
        comman = None
        if valcfg.report_addr == "local":
            comman = communications.EmbeddedServer(valcfg.sid)
            io.console.print_item("Running a local instance")
        else:
            comman = communications.RemoteServer(
                valcfg.sid, valcfg.report_addr)
            io.console.print_item("Listening on {}".format(comman.endpoint))
        MetaConfig.root.set_internal('comman', comman)

    io.console.print_item("Init the global Orchestrator")
    MetaConfig.root.set_internal('orchestrator', Orchestrator())

    io.console.print_item("Save Configurations into {}".format(valcfg.output))
    build_man.save_config(MetaConfig.root)


def find_files_to_process(path_dict):
    """Lookup for test files to process, from the list of paths provided as
    parameter.

    The given `path_dict` is a dict, where keys are path labels given by the
    user, while values are the actual path. This function then returns a
    two-list tuple, one being files needing preprocessing (setup), the other
    being static configuration files (pcvs.yml)

    Each list element is a tuple:
         * origin label
         * subtree from this label leading to the actual file
         * file basename (either "pcvs.setup" or "pcvs.yml")

    :param path_dict: tree of paths to look for
    :type path_dict: dict
    :return: a tuple with two lists
    :rtype: tuple
    """
    setup_files = list()
    yaml_files = list()

    # discovery may take a while with some systems
    # iterate over user directories
    for label, path in path_dict.items():
        # for each, walk through the tree
        for root, dirs, list_files in os.walk(path):
            last_dir = os.path.basename(root)
            # if the current dir is a 'special' one, discard
            if last_dir in [NAME_SRCDIR, NAME_BUILDIR, "build_scripts"]:
                io.console.debug("skip {}".format(root))
                # set dirs to null, avoiding os.wal() to go further in that dir
                dirs[:] = []
                continue
            # otherwise, save the file
            for f in list_files:
                # [1:] to remove extra '/'
                subtree = os.path.relpath(root, path)
                if subtree == ".":
                    subtree = None
                if 'pcvs.setup' == f:
                    setup_files.append((label, subtree, f))
                elif 'pcvs.yml' == f or 'pcvs.yml.in' == f:
                    yaml_files.append((label, subtree, f))
    return (setup_files, yaml_files)


def process_files():
    """Process the test-suite generation.

    It includes walking through user directories to find definitions AND
    generating the associated tests.

    :raises TestUnfoldError: An error occured while processing files
    """
    io.console.print_item("Locate benchmarks from user directories")
    setup_files, yaml_files = find_files_to_process(
        MetaConfig.root.validation.dirs)

    io.console.debug("Found setup files: {}".format(
        pprint.pformat(setup_files)))
    io.console.debug("Found static files: {}".format(
        pprint.pformat(yaml_files)))

    errors = []

    io.console.print_item("Extract tests from dynamic definitions ({} found)".format(len(setup_files)))
    errors += process_dyn_setup_scripts(setup_files)
    io.console.print_item("Extract tests from static definitions ({} found)".format(len(yaml_files)))
    errors += process_static_yaml_files(yaml_files)

    if len(errors):
        #**{e[0]: e[1] for e in errors}
        raise TestException.TestExpressionError(
                        reason="Test-suites failed to be parsed.",
                        **{e[0]: e[1].dbg for e in errors})


def process_spack():

    if not shutil.which('spack'):
        io.console.warn(
            "Unable to parse Spack recipes without having Spack in $PATH")
        return
    io.console.print_item("Build test-bases from Spack recipes")
    label = "spack"
    path = "/spack"
    MetaConfig.root.validation.dirs[label] = path
    build_man = MetaConfig.root.get_internal('build_manager')

    _, _, rbuild, _ = testing.generate_local_variables(label, '')
    build_man.save_extras(os.path.relpath(rbuild, build_man.prefix), dir=True, export=False)

    for spec in io.console.progress_iter(MetaConfig.root.validation.spack_recipe):
        _, _, _, cbuild = testing.generate_local_variables(label, spec)
        build_man.save_extras(os.path.relpath(cbuild, build_man.prefix), dir=True, export=False)
        pvSpack.generate_from_variants(spec, label, spec)


def build_env_from_configuration(current_node, parent_prefix="pcvs"):
    """create a flat dict of variables mapping to the actual configuration.

    In order to "pcvs.setup" to read current configuration, the whole config is
    serialized into shell variables. Purpose of this function is to flatten the
    configuration tree into env vars, each tree level being divided with an
    underscore.

    This function is called recursively to walk through the whole tree.

    :example:
        The `compiler.cc` config node become `$compiler_cc_program=<...>`

    :param current_node: current node to flatten
    :type current_node: dict
    :param parent_prefix: prefix used to name vars at this depth, defaults to "pcvs"
    :type parent_prefix: str, optional
    :return: a flat dict of the whole configuration, keys are shell variables.
    :rtype: dict
    """
    env_dict = dict()
    for k, v in current_node.items():
        if v is None:
            v = ''
        if isinstance(v, dict):
            env_dict.update(build_env_from_configuration(
                v, parent_prefix+"_"+k))
            continue
        elif v is None:
            v = ''
        elif isinstance(v, list):
            v = " ".join(map(str, v))
        else:
            v = str(v)
        k = "{}_{}".format(parent_prefix, k).replace('.', '_')
        env_dict[k] = v
    return env_dict


def process_dyn_setup_scripts(setup_files):
    """Process dynamic test files and generate associated tests.

    This function executes pcvs.setup files after deploying the environment (to
    let these scripts access it). It leads to generate "pcvs.yml" files, then
    processed to construct tests.

    :param setup_files: list of tuples, each mapping a single pcvs.setup file
    :type setup_files: tuple
    :return: list of errors encountered while processing.
    :rtype: list
    """
    err = []
    io.console.info("Convert configuration to Shell variables")
    env = os.environ.copy()
    env_config = build_env_from_configuration(MetaConfig.root)
    env.update(env_config)
    
    with open(os.path.join(MetaConfig.root.validation.output, NAME_BUILD_CONF_SH), 'w') as fh:
        fh.write(utils.str_dict_as_envvar(env_config))
        fh.close()

    io.console.info("Iteration over files")
    for label, subprefix, fname in io.console.progress_iter(setup_files):
        io.console.debug("process {} ({})".format(subprefix, label))
        base_src, cur_src, base_build, cur_build = testing.generate_local_variables(
            label, subprefix)
        # prepre to exec pcvs.setup script
        # 1. setup the env
        env['pcvs_src'] = base_src
        env['pcvs_testbuild'] = base_build

        if not os.path.isdir(cur_build):
            os.makedirs(cur_build)

        f = os.path.join(cur_src, fname)

        if not subprefix:
            subprefix = ""
        # Run the script
        try:
            fds = subprocess.Popen([f, subprefix], env=env,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            fdout, fderr = fds.communicate()

            if fds.returncode != 0:
                raise RunException.NonZeroSetupScript(rc=fds.returncode, err=fderr, file=f)

            #### should be enabled only in debug mode
            # flush the output to $BUILD/pcvs.yml
            #out_file = os.path.join(cur_build, 'pcvs.yml')
            #with open(out_file, 'w') as fh:
                #fh.write(fdout.decode('utf-8'))
        except CalledProcessError as e:
            err.append((f, RunException.ProgramError(file=f)))
            continue
        except RunException.NonZeroSetupScript as e:
            err.append((f, e))
            io.console.info("Setup Failed ({}): {}".format(f, e.dbg['err'].decode('utf-8')))
            continue
        
        out = fdout.decode('utf-8')
        if not out:
            # pcvs.setup did not output anything
            continue
        
        
        # Now create the file handler
        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.TFILE_BEFORE)
        obj = TestFile(file_in="<stream>",
                       path_out=cur_build,
                       label=label,
                       prefix=subprefix
                       )
        
        obj.load_from_str(out)
        obj.save_yaml()
        
        obj.process()
        obj.flush_sh_file()
        MetaConfig.root.get_internal(
            "pColl").invoke_plugins(Plugin.Step.TFILE_AFTER)
    return err


def process_static_yaml_files(yaml_files):
    """Process 'pcvs.yml' files to contruct the test base.

    :param yaml_files: list of tuples, each describing a single input file.
    :type yaml_files: list
    :return: list of encountered errors while processing
    :rtype: list
    """
    err = []
    io.console.info("Iteration over files")
    for label, subprefix, fname in io.console.progress_iter(yaml_files):
        _, cur_src, _, cur_build = testing.generate_local_variables(
            label, subprefix)
        if not os.path.isdir(cur_build):
            os.makedirs(cur_build)
        f = os.path.join(cur_src, fname)

        try:
            obj = TestFile(file_in=f,
                           path_out=cur_build,
                           label=label,
                           prefix=subprefix
                           )
            obj.process()
            obj.flush_sh_file()
        except Exception as e:
            #raise e
            err.append((f, e))
            io.console.info("{} (failed to parse): {}".format(f, e))
    return err


def anonymize_archive():
    """Erase from results any undesired output from the generated archive.

    This process is disabled by default as it may increase significantly the
    validation process on large test bases.
    .. note::
        It does not alter results in-place, only the generated archive. To
        preserve the anonymization, only the archive must be exported/shared,
        not the actual build directory.
    """
    config = MetaConfig.root.validation
    outdir = config.output
    for root, _, files in os.walk(config.output):
        for f in files:
            if not f.endswith(('.xml', '.json', '.yml',
                               '.txt', '.md', '.html')):
                continue
            with fileinput.FileInput(os.path.join(root, f),
                                     inplace=True,
                                     backup=".raw") as fh:
                for line in fh:
                    # TODO: add more patterns (user-defined ? )
                    print(
                        line.replace(outdir, '${PCVS_RUN_DIRECTORY}')
                            .replace(os.environ['HOME'], '${HOME}')
                            .replace(os.environ['USER'], '${USER}'),
                        end='')


def terminate():
    """Finalize a validation run.

    This include generating & anonymizing (if needed) the archive.

    :raises ProgramError: Problem occured while invoking the archive tool.
    """
    MetaConfig.root.get_internal(
        "pColl").invoke_plugins(Plugin.Step.END_BEFORE)

    build_man = MetaConfig.root.get_internal('build_manager')
    outdir = MetaConfig.root.validation.output

    io.console.print_section("Prepare results")
    io.console.move_debug_file(outdir)
    archive_path = build_man.create_archive()

    # if MetaConfig.root.validation.anonymize:
    #    io.console.print_item("Anonymize data")
    #    anonymize_archive()

    comman = MetaConfig.root.get_internal("comman")
    if comman:
        io.console.print_item("Close connection to Reporting Server")
        comman.close_connection()
    MetaConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.END_AFTER)
    build_man.finalize()


def dup_another_build(build_dir, outdir):
    """Clone another build directory to start this validation upon it.

    It allows to save test-generation time if the validation is re-run under the
    exact same terms (identical configuration & tests).

    :param build_dir: the build directory to copy resource from
    :type build_dir: str
    :param outdir: where data will be copied to.
    :type outdir: str
    :return: the whole configuration loaded from the dup'd build directory
    :rtype: dict
    """
    global_config = None

    # First, load the whole config
    with open(os.path.join(build_dir, NAME_BUILD_CONF_FN), 'r') as fh:
        d = MetaDict(YAML(typ='safe').load(fh))
        global_config = MetaConfig(d)

    # first, clear fields overridden by current run
    global_config.validation.output = outdir
    global_config.validation.reused_build = build_dir
    global_config.validation.buildcache = os.path.join(outdir, NAME_BUILD_CACHEDIR)

    # second, copy any xml/sh files to be reused
    for root, _, files, in os.walk(os.path.join(build_dir, "test_suite")):
        for f in files:
            if f in ('dbg-pcvs.yml', 'list_of_tests.sh'):
                src = os.path.join(root, f)
                dest = os.path.join(outdir,
                                    os.path.relpath(
                                        src,
                                        start=os.path.abspath(build_dir))
                                    )

                utils.copy_file(src, dest)

    # other files
    for f in (NAME_BUILD_CONF_SH):
        src = os.path.join(build_dir, f)
        dest = os.path.join(outdir,
                            os.path.relpath(
                                src,
                                start=os.path.abspath(build_dir))
                            )
        if not os.path.isfile(src):
            continue

        utils.copy_file(src, dest)

    return global_config
