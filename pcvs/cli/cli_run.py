import os
import sys
from datetime import datetime

from pcvs import NAME_BUILDFILE, NAME_RUN_CONFIG_FILE, io
from pcvs.io import Verbosity
from pcvs.backend import bank as pvBank
from pcvs.backend import profile as pvProfile
from pcvs.backend import run as pvRun
from pcvs.backend import session as pvSession
from pcvs.cli import cli_bank, cli_profile
from pcvs.helpers import exceptions, system, utils
from pcvs.orchestration.publishers import BuildDirectoryManager

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click


def iterate_dirs(ctx, param, value) -> dict:
    """Validate directories provided by users & format them correctly.

    Set the defaul label for a given path if not specified & Configure default
    directories if none was provided.

    :param ctx: Click Context
    :type ctx: :class:`Click.Context`
    :param param: The arg targeting the function
    :type param: str
    :param value: The value given by the user:
    :type value: List[str] or str
    :return: properly formatted dict of user directories, keys are labels.
    :rtype: dict
    """
    list_of_dirs = dict()
    if not value:  # if not specified
        return None
    else:  # once specified
        err_msg = ""
        for d in value:
            if ':' in d:  # split under LABEL:PATH semantics
                [label, testpath] = d.split(':')
                testpath = os.path.abspath(testpath)
            else:  # otherwise, LABEL = dirname
                testpath = os.path.abspath(d)
                label = os.path.basename(testpath)

            # if label already used for a different path
            if label in list_of_dirs.keys() and testpath != list_of_dirs[label]:
                err_msg += "- '{}': Used more than once\n".format(
                    label.upper())
            elif not os.path.isdir(testpath):
                err_msg += "- '{}': No such directory\n".format(testpath)
            # else, add it
            else:
                list_of_dirs[label] = testpath
        if len(err_msg):
            raise click.BadArgumentUsage("\n".join([
                "While parsing user directories:",
                '{}'.format(err_msg),
                "please see '--help' for more information"
            ]))
    return list_of_dirs


def compl_list_dirs(ctx, args, incomplete) -> list:  # pragma: no cover
    """directory completion function.

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """
    abspath = os.path.abspath(incomplete)

    if ":" in incomplete:
        label, path = incomplete.split(":", 1)
        label += ":"
    obj = click.Path(exists=True, dir_okay=True, file_okay=False)
    obj.shell_complete(ctx, args, incomplete)


def handle_build_lockfile(exc=None):
    """Remove the file lock in build dir if the application stops abrubtly.

    This function will automatically forward the raising exception to the next
    handler.

    :raises Exception: any exception triggering this handler
    :param exc: The raising exception.
    :type exc: Exception
    """
    if system.MetaConfig.root:
        prefix = os.path.join(
            system.MetaConfig.root.validation.output, NAME_BUILDFILE)
        if utils.is_locked(prefix):
            if utils.get_lock_owner(prefix)[1] == os.getpid():
                utils.unlock_file(prefix)

    if exc:
        raise exc


@click.command(name="run", short_help="Run a validation")
@click.option("-p", "--profile", "profilename", default=None,
              shell_complete=cli_profile.compl_list_token,
              type=str, show_envvar=True,
              help="Existing and valid profile supporting this run")
@click.option("-o", "--output", "output", default=None, show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="F directory where PCVS is allowed to store data")
@click.option("-c", '--settings-file', "settings_file",
              default=None, show_envvar=True, type=click.File('r'),
              help="Invoke file gathering validation options")
@click.option("--detach", "detach",
              default=None, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously (WIP)")
@click.option("-f/-F", "--override/--no-override", "override",
              default=None, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output directory")
@click.option("-d", "--dry-run", "simulated",
              default=False, is_flag=True,
              help="Reproduce the whole process without running tests")
@click.option("-a", "--anonymize", "anon",
              default=None, is_flag=True,
              help="Purge the results from sensitive data (HOME, USER...)")
@click.option("-b", "--bank", "bank", default=None, shell_complete=cli_bank.compl_bank_projects,
              help="Which bank will store the run in addition to the archive")
@click.option("-m", "--message", "msg", default=None,
              help="Message to store the run (if bank is enabled)")
@click.option("--duplicate", "dup", default=None,
              type=click.Path(exists=True, file_okay=False), required=False,
              help="Reuse old test directories (no DIRS required)")
@click.option("-r", "--report", "enable_report", show_envvar=True,
              is_flag=True, default=None,
              help="Attach a webview server to the current session run.")
@click.option("--report-uri", "report_addr", default=None, type=str,
              help="Override default Server address")
@click.option("-g", "--generate-only", "generate_only", is_flag=True, default=None,
              help="Rebuild the test-base, populating resources for `pcvs exec`")
@click.option('-t', "--timeout", "timeout", show_envvar=True, type=int, default=None,
              help="PCVS process timeout")
@click.option("-S", "--successful", "only_success", is_flag=True, default=None,
              help="Return non-zero exit code if a single test has failed")
@click.option("-s", "--spack-recipe", "spack_recipe", type=str, multiple=True,
              help="Build test-suites based on Spack recipes")
@click.option("-P", "--print", "print_level", type=click.Choice(['none', 'errors', 'all']),
              default=None, help="Enable test output to be printed depending on its status")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
@io.capture_exception(Exception)
@io.capture_exception(Exception, handle_build_lockfile)
@io.capture_exception(KeyboardInterrupt, handle_build_lockfile)
def run(ctx, profilename, output, detach, override, anon, settings_file,
        generate_only, spack_recipe, print_level, simulated, bank, msg, dup,
        dirs, enable_report, report_addr, only_success, timeout) -> None:
    """
    Execute a validation suite from a given PROFILE.

    By default the current directory is scanned to find test-suites to run.
    May also be provided as a list of directories as described by tests
    found in DIRS.
    """
    
    io.console.info("PRE-RUN: start")
    # first, prepare raw arguments to be usable
    if output is not None:
        output = os.path.abspath(output)

    if print_level and print_level != "none":
        # any --print option will imply to disable packed rich console view
        # --> enable verbose mode
        io.console.verbose = Verbosity.DETAILED
        ctx.obj['verbose'] = str(io.console.verbose)

    global_config = system.MetaConfig()
    system.MetaConfig.root = global_config
    global_config.set_internal("pColl", ctx.obj['plugins'])

    # then init the configuration
    if settings_file is None:
        # detect ?
        detect = os.path.join(os.getcwd(), NAME_RUN_CONFIG_FILE)
        settings_file = detect if os.path.isfile(detect) else None
    io.console.debug(
        "PRE-RUN: load settings from local file: {}".format(settings_file))
    val_cfg = global_config.bootstrap_validation_from_file(settings_file)

    # save 'run' parameters into global configuration
    val_cfg.set_ifdef('datetime', datetime.now())
    val_cfg.set_ifdef('verbose', ctx.obj['verbose'])
    val_cfg.set_ifdef('print_level', print_level)
    val_cfg.set_ifdef('color', ctx.obj['color'])
    val_cfg.set_ifdef('output', output)
    val_cfg.set_ifdef('background', detach)
    val_cfg.set_ifdef('override', override)
    val_cfg.set_ifdef('simulated', simulated)
    val_cfg.set_ifdef('onlygen', generate_only)
    val_cfg.set_ifdef('anonymize', anon)
    val_cfg.set_ifdef('reused_build', dup)
    val_cfg.set_ifdef('default_profile', profilename)
    val_cfg.set_ifdef('target_bank', bank)
    val_cfg.set_ifdef('message', msg)
    val_cfg.set_ifdef('enable_report', enable_report)
    val_cfg.set_ifdef('report_addr', report_addr)
    val_cfg.set_ifdef('timeout', timeout)
    val_cfg.set_ifdef('spack_recipe', spack_recipe)
    val_cfg.set_ifdef('only_success', only_success)
    val_cfg.set_ifdef('buildcache', os.path.join(val_cfg.output, 'cache'))

    # if dirs not set by config file nor CLI
    if not dirs and not val_cfg.dirs:
        dirs = dict()
        if not spack_recipe:
            testpath = os.getcwd()
            dirs = {os.path.basename(testpath): testpath}

    # not overriding if dirs is None
    val_cfg.set_ifdef("dirs", dirs)

    if bank is not None:
        obj = pvBank.Bank(token=bank, path=None)
        io.console.debug(
            "PRE-RUN: configure target bank: {}".format(obj.name))
        if not obj.exists():
            raise click.BadOptionUsage(
                "--bank", "'{}' bank does not exist".format(obj.name))
        obj.disconnect()

    # BEFORE the build dir still does not exist !
    buildfile = os.path.join(val_cfg.output, NAME_BUILDFILE)
    if os.path.exists(val_cfg.output):
        # careful if the build dir does not exist
        # the condition above may be executed concurrently
        # by two runs, inducing parallel execution in the same dir
        # TODO.
        if not utils.trylock_file(buildfile):
            if val_cfg.override:
                utils.lock_file(buildfile, force=True)
            else:
                raise exceptions.RunException.InProgressError(path=val_cfg.output,
                                                              lockfile=buildfile,
                                                              owner_pid=utils.get_lock_owner(buildfile))

    elif not os.path.exists(val_cfg.output):
        io.console.debug(
            "PRE-RUN: Prepare output directory: {}".format(val_cfg.output))
        os.makedirs(val_cfg.output)

    # check if another build should reused
    # this avoids to re-run combinatorial system twice
    if val_cfg.reused_build is not None:
        io.console.info("PRE-RUN: Clone previous build to be reused")
        try:
            io.console.debug(
                "PRE-RUN: previous build: {}".format(val_cfg.reused_build))
            global_config = pvRun.dup_another_build(
                val_cfg.reused_build, val_cfg.output)
            # TODO: Currently nothing can be overriden from cloned build except:
            # - 'output'
        except FileNotFoundError:
            raise click.BadOptionUsage(
                "--duplicate", "{} is not a valid build directory!".format(val_cfg.reused_build))
    else:
        # otherwise create own settings command block
        io.console.info(
            "PRE-RUN: Profile lookup: {}".format(val_cfg.default_profile))
        (scope, _, label) = utils.extract_infos_from_token(val_cfg.default_profile,
                                                           maxsplit=2)
        pf = pvProfile.Profile(label, scope)
        if not pf.is_found():
            raise click.BadOptionUsage(
                "--profile", "Profile '{}' not found".format(val_cfg.default_profile))
        pf.load_from_disk()
        pf.check()

        val_cfg.set_ifdef('pf_name', pf.full_name)
        val_cfg.set_ifdef('pf_hash', pf.get_unique_id())
        global_config.bootstrap_from_profile(pf.dump())

    the_session = pvSession.Session(val_cfg.datetime, val_cfg.output)
    the_session.register_callback(callback=pvRun.process_main_workflow)

    io.console.info("PRE-RUN: Session to be started")
    if val_cfg.background:
        sid = the_session.run_detached(the_session)
        print(
            "Session successfully started, ID {}".format(sid))

    else:
        sid = the_session.run(the_session)
        utils.unlock_file(buildfile)
       
    final_rc = the_session.rc if only_success else 0
    sys.exit(final_rc)
