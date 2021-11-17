import fileinput
import os
import pprint
import shutil
import signal
import subprocess
import time
from subprocess import CalledProcessError

from ruamel.yaml import YAML

from pcvs import (NAME_BUILD_CONF_FN, NAME_BUILD_RESDIR, NAME_BUILDFILE,
                  NAME_BUILDIR, NAME_SRCDIR)
from pcvs.backend import bank as pvBank
from pcvs.helpers import communications, criterion, log, utils
from pcvs.helpers.exceptions import RunException
from pcvs.helpers.system import MetaConfig, MetaDict
from pcvs.orchestration import Orchestrator
from pcvs.plugins import Plugin
from pcvs.testing.tedesc import TEDescriptor
from pcvs.testing.testfile import TestFile, load_yaml_file


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


def str_dict_as_envvar(d):
    """Convert a dict to a list of shell-compliant variable strings.

    The final result is a regular multiline str, each line being an entry.

    :param d: the dict containing env vars to serialize
    :type d: dict
    :return: the str, containing mulitple lines, each of them being a var.
    :rtype: str
    """
    return "\n".join(["{}='{}'".format(i, d[i]) for i in sorted(d.keys())])


def display_summary(the_session):
    """Display a summary for this run, based on profile & CLI arguments."""
    cfg = MetaConfig.root.validation

    log.manager.print_section("Global Information")
    log.manager.print_item("Date of execution: {}".format(
        MetaConfig.root.validation.datetime.strftime("%c")))
    log.manager.print_item("Run by: {} <{}>".format(
        cfg.author.name, cfg.author.email))
    log.manager.print_item("Active session ID: {}".format(the_session.id))
    log.manager.print_item("Loaded profile: '{}'".format(cfg.pf_name))
    log.manager.print_item("Build stored to: {}".format(cfg.output))
    log.manager.print_item("Criterion matrix size per job: {}".format(
        MetaConfig.root.get_internal("comb_cnt")
    ))

    if cfg.target_bank:
        log.manager.print_item("Bank Management: {}".format(cfg.target_bank))
    log.manager.print_item("Verbosity: {}".format(
        log.manager.get_verbosity_str().capitalize()))
    log.manager.print_section("User directories:")
    width = max([len(i) for i in cfg.dirs])
    for k, v in cfg.dirs.items():
        log.manager.print_item("{:<{width}}: {:<{width}}".format(
            k.upper(),
            v,
            width=width))

    log.manager.print_section("Globally loaded plugins:")
    MetaConfig.root.get_internal("pColl").show_enabled_plugins()

    log.manager.print_section("Orchestration infos")
    MetaConfig.root.get_internal("orchestrator").print_infos()

    if cfg.simulated is True:
        log.manager.warn([
            "==============================================",
            ">>>> DRY-RUN : TEST EXECUTION IS EMULATED <<<<",
            "=============================================="])


def stop_pending_jobs(exc=None):
    orch = MetaConfig.root.get_internal('orchestrator')
    if orch:
        orch.stop()
    if exc:
        raise exc


@log.manager.capture_exception(Exception, stop_pending_jobs)
def process_main_workflow(the_session=None):
    """Main run.py entry point, triggering a PCVS validation run.

    This function is called by session management and may be run within an
    active terminal or as a detached process.

    :param the_session: the session handler this run is connected to, defaults to None
    :type the_session: :class:`Session`, optional
    """
    log.manager.info("RUN: Session start")
    global_config = MetaConfig.root
    valcfg = global_config.validation
    rc = 0

    log.manager.set_logfile(valcfg.runlog is not None, valcfg.runlog)
    valcfg.sid = the_session.id

    log.manager.print_banner()
    log.manager.print_header("Initialization")
    # prepare PCVS and third-party tools
    prepare()

    if valcfg.reused_build is not None:
        log.manager.print_section("Reusing previously generated inputs")
    else:
        log.manager.print_section("Load Test Suites")
        start = time.time()
        process()
        end = time.time()
        log.manager.print_section(
            "===> Processing done in {:<.3f} sec(s)".format(end-start))

    log.manager.print_header("Summary")
    display_summary(the_session)

    if valcfg.onlygen:
        log.manager.warn(
            ["====================================================",
             "Tests won't be run. This program will now stop.",
             "You may list runnable tests with `pcvs exec --list`",
             "or execute one with `pcvs exec <testname>`",
             "===================================================="
             ])
        return 0

    log.manager.print_header("Execution")
    rc += MetaConfig.root.get_internal('orchestrator').run(the_session)

    log.manager.print_header("Finalization")
    # post-actions to build the archive, post-process the webview...
    terminate()

    bank_token = valcfg.target_bank
    if bank_token is not None:
        bank = pvBank.Bank(token=bank_token)
        pref_proj = bank.preferred_proj
        if bank.exists():
            log.manager.print_item("Upload results to bank: '{}{}'".format(
                bank.name.upper(),
                " (@{})".format(pref_proj) if pref_proj else ""
            ))
            bank.connect_repository()
            bank.save_from_buildir(
                None,
                os.path.join(valcfg.output)
            )

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
    utils.check_valid_program(MetaConfig.root.machine.job_manager.run.program)
    utils.check_valid_program(MetaConfig.root.machine.job_manager.run.wrapper)
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.batch.program)
    utils.check_valid_program(
        MetaConfig.root.machine.job_manager.batch.wrapper)
    return
    # TODO: need to handle package_manager commands to process below
    # maybe a dummy testfile should be used
    utils.check_valid_program(MetaConfig.root.compiler.commands.cc)
    utils.check_valid_program(MetaConfig.root.compiler.commands.cxx)
    utils.check_valid_program(MetaConfig.root.compiler.commands.fc)
    utils.check_valid_program(MetaConfig.root.compiler.commands.f77)
    utils.check_valid_program(MetaConfig.root.compiler.commands.f90)
    utils.check_valid_program(MetaConfig.root.runtime.program)


def prepare():
    """Prepare the environment for a validation run.

    This function prepares the build dir, create trees...
    """
    log.manager.print_section("Prepare environment")
    valcfg = MetaConfig.root.validation

    utils.start_autokill(valcfg.timeout)

    log.manager.print_item("Check whether build directory is valid")
    buildir = os.path.join(valcfg.output, "test_suite")
    if not os.path.exists(buildir):
        os.makedirs(buildir)
    # if a previous build exists
    if valcfg.reused_build is None:
        log.manager.print_item("Cleaning up {}".format(buildir), depth=2)
        utils.create_or_clean_path(buildir)
    utils.create_or_clean_path(os.path.join(
        valcfg.output, NAME_BUILDFILE))
    utils.create_or_clean_path(os.path.join(
        valcfg.output, 'webview'), dir=True)
    utils.create_or_clean_path(os.path.join(valcfg.output, NAME_BUILD_CONF_FN))
    utils.create_or_clean_path(os.path.join(valcfg.output, 'conf.env'))
    utils.create_or_clean_path(os.path.join(
        valcfg.output, 'save_for_export'), dir=True)
    utils.create_or_clean_path(os.path.join(
        valcfg.output, NAME_BUILD_RESDIR), dir=True)
    utils.create_or_clean_path(valcfg.buildcache, dir=True)

    log.manager.print_item("Create test subtrees")
    os.makedirs(buildir, exist_ok=True)
    for label in valcfg.dirs.keys():
        os.makedirs(os.path.join(buildir, label), exist_ok=True)
    open(os.path.join(valcfg.output, NAME_BUILDFILE), 'w').close()

    log.manager.print_item("Ensure user-defined programs exist")
    __check_defined_program_validity()

    log.manager.print_item("Init & expand criterions")
    criterion.initialize_from_system()
    # Pick on criterion used as 'resources' by JCHRONOSS
    # this is set by the run configuration
    # TODO: replace resource here by the one read from config
    TEDescriptor.init_system_wide('n_node')

    log.manager.print_item("Init the global Orchestrator")
    MetaConfig.root.set_internal('orchestrator', Orchestrator())

    if valcfg.enable_report:
        log.manager.print_section("Connection to the Reporting Server")
        comman = None
        if valcfg.report_addr == "local":
            comman = communications.EmbeddedServer(valcfg.sid)
            log.manager.print_item("Running a local instance")
        else:
            comman = communications.RemoteServer(
                valcfg.sid, valcfg.report_addr)
            log.manager.print_item("Listening on {}".format(comman.endpoint))
        MetaConfig.root.set_internal('comman', comman)

    log.manager.print_item("Save Configurations into {}".format(valcfg.output))
    conf_file = os.path.join(valcfg.output, NAME_BUILD_CONF_FN)
    with open(conf_file, 'w') as conf_fh:
        handler = YAML(typ='safe')
        handler.default_flow_style = None
        handler.dump(MetaConfig.root.dump_for_export(), conf_fh)


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
                log.manager.debug("skip {}".format(root))
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


def process():
    """Process the test-suite generation.

    It includes walking through user directories to find definitions AND
    generating the associated tests.

    :raises TestUnfoldError: An error occured while processing files
    """
    log.manager.print_item("Locate benchmarks from user directories")
    setup_files, yaml_files = find_files_to_process(
        MetaConfig.root.validation.dirs)

    log.manager.debug("Found setup files: {}".format(
        pprint.pformat(setup_files)))
    log.manager.debug("Found static files: {}".format(
        pprint.pformat(yaml_files)))

    errors = []

    log.manager.print_item("Extract tests from dynamic definitions")
    errors += process_dyn_setup_scripts(setup_files)
    log.manager.print_item("Extract tests from static definitions")
    errors += process_static_yaml_files(yaml_files)

    if len(errors):
        log.manager.err(["Test-suites failed to be parsed, with the following errors:"] +
                        ["\t-{}: {}".format(e[0], e[1]) for e in errors]
                        )
        raise RunException.TestUnfoldError("See previous errors above.")


def build_env_from_configuration(current_node, parent_prefix="pcvs"):
    """create a flat dict of variables mapping to the actual configuration.

    In order to "pcvs.setup" to read current configuration, the whole config is
    serialized into shell variables. Purpose of this function is to flatten the
    configuration tree into env vars, each tree level being divided with an
    underscore.

    This function is called recursively to walk through the whole tree.

    :example:
        The `compiler.commands.cc` config node become `$compiler_commands_cc=<...>`

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
    log.manager.info("Convert configuration to Shell variables")
    env = os.environ.copy()
    env.update(build_env_from_configuration(MetaConfig.root))

    env_script = os.path.join(MetaConfig.root.validation.output, 'conf.env')
    with open(env_script, 'w') as fh:
        fh.write(str_dict_as_envvar(env))
        fh.close()

    log.manager.info("Iteration over files")
    with log.progbar(setup_files, print_func=print_progbar_walker) as itbar:
        for label, subprefix, fname in itbar:
            log.manager.debug("process {} ({})".format(subprefix, label))
            base_src, cur_src, base_build, cur_build = utils.generate_local_variables(
                label, subprefix)

            # prepre to exec pcvs.setup script
            # 1. setup the env
            env['pcvs_src'] = base_src
            env['pcvs_testbuild'] = base_build
            te_node = None
            out_file = None

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
                    raise subprocess.CalledProcessError(fds.returncode, '')

                # flush the output to $BUILD/pcvs.yml
                out_file = os.path.join(cur_build, 'pcvs.yml')
                with open(out_file, 'w') as fh:
                    fh.write(fdout.decode('utf-8'))
                te_node = load_yaml_file(
                    out_file, base_src, base_build, subprefix)
            except CalledProcessError:
                if fds.returncode != 0:
                    err.append((f, "(exit {}): {}".format(
                        fds.returncode, fderr.decode('utf-8'))))
                    log.manager.info("EXEC FAILED: {}: {}".format(
                        f, fderr.decode('utf-8')))
                continue

            # If the script did not generate any output, skip
            if te_node is None:  # empty file
                continue

            # Now create the file handler
            MetaConfig.root.get_internal(
                "pColl").invoke_plugins(Plugin.Step.TFILE_BEFORE)
            obj = TestFile(file_in=out_file,
                           path_out=cur_build,
                           data=te_node,
                           label=label,
                           prefix=subprefix
                           )
            obj.load_from_str(fdout.decode('utf-8'))
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
    log.manager.info("Iteration over files")
    with log.progbar(yaml_files, print_func=print_progbar_walker) as iterbar:
        for label, subprefix, fname in iterbar:
            _, cur_src, _, cur_build = utils.generate_local_variables(
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
                err.append((f, e))
                log.manager.info("{} (failed to parse): {}".format(f, e))
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
    archive_prefix = os.path.join(config.output, 'save_for_export')
    outdir = config.output
    for root, _, files in os.walk(archive_prefix):
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


def save_for_export(f, dest=None):
    """Add a resource to the archive to be exported.

    Copy a source file to a destination prefix. The root build directory is
    replaced with $buildir/save_for_export, the relative subtree is preserved.

    If 'dest' is set, the default target directory may be changed.

    :param f: the source file to be saved (absolute path)
    :type f: str
    :param dest: the destination directory, defaults to None
    :type dest: str, optional
    :raises UnclassifiableError: input file is not a file or a directory
    :raises NotFoundError: source or target resource cannot be determined
    """
    config = MetaConfig.root.validation
    # if dest is not given, 'dest' will be the same dirtree with
    # extra 'safe_for_export' sudir below 'outdir'
    # otherwise, just use the given dest instead of replacing
    if dest is None:
        dest = f
    dest = dest.replace(config.output, os.path.join(
        config.output, 'save_for_export'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    try:
        if os.path.isfile(f):
            shutil.copyfile(f, dest)
        elif os.path.isdir(f):
            shutil.copytree(f, dest)
        else:
            raise RunException.UnclassifiableError("{}".format(f))
    except FileNotFoundError as e:
        raise RunException.NotFoundError(e, f)


def terminate():
    """Finalize a validation run.

    This include generating & anonymizing (if needed) the archive.

    :raises ProgramError: Problem occured while invoking the archive tool.
    """
    MetaConfig.root.get_internal(
        "pColl").invoke_plugins(Plugin.Step.END_BEFORE)
    archive_name = "pcvsrun_{}.tar.gz".format(
        MetaConfig.root.validation.datetime.strftime('%Y%m%d%H%M%S'))
    outdir = MetaConfig.root.validation.output

    log.manager.print_section("Prepare results")

    save_for_export(os.path.join(outdir, NAME_BUILD_RESDIR))
    save_for_export(os.path.join(outdir, NAME_BUILD_CONF_FN))

    if MetaConfig.root.validation.anonymize:
        log.manager.print_item("Anonymize data")
        anonymize_archive()

    log.manager.print_item("Generate the archive: {}".format(archive_name))

    with utils.cwd(outdir):
        cmd = [
            "tar",
            "czf",
            "{}".format(archive_name),
            "save_for_export"
        ]
        try:
            log.manager.debug('cmd: {}'.format(" ".join(cmd)))
            subprocess.check_call(cmd)
        except CalledProcessError as e:
            raise RunException.ProgramError(e, cmd)

    comman = MetaConfig.root.get_internal("comman")
    if comman:
        log.manager.print_item("Close connection to Reporting Server")
        comman.close_connection()
    MetaConfig.root.get_internal("pColl").invoke_plugins(Plugin.Step.END_AFTER)


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
    global_config.validation.buildcache = os.path.join(outdir, 'cache')

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
    for f in ('conf.env'):
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
