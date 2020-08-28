import os
import time
import click

from pcvsrt.cli.run import backend as pvRun
from pcvsrt.cli.profile import backend as pvProfile
from pcvsrt.cli.profile import commands as cmdProfile
from pcvsrt.helpers import io, log


def iterate_dirs(ctx, param, value) -> dict:
    list_of_dirs = dict()
    if not value:  # if not specified
        testpath = os.getcwd()
        label = os.path.basename(testpath)
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
                err_msg += "- '{}': Used more than once\n".format(label.upper())
            elif not os.path.isdir(testpath):
                err_msg += "- '{}': No such directory\n".format(testpath)   
            # else, add it
            else:
                list_of_dirs[label] = testpath
        if len(err_msg):
            log.err(
                "Errors occured while parsing user directories:",
                err_msg,
                "please see '--help' for more information", abort=1)

    return list_of_dirs


@click.command(name="run", short_help="Run a validation")
@click.option("-p", "--profile", "profilename", default="default",
              autocompletion=cmdProfile.compl_list_token,
              type=str, show_envvar=True, help="an existing profile")
@click.option("-o", "--output", "output", default=".", show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="Where artefacts will be stored during/after the run")
@click.option("-c", "--set-defaults", "set_default",
              default=None, is_flag=True,
              help="Set default values for run options (WIP)")
#@click.option("-l", "--tee", "log", show_envvar=True,
#              default=False, is_flag=True,
#              help="Log the whole stdout/stderr")
@click.option("-d", "--detach", "detach",
              default=True, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously")
@click.option("--status", "status",
              default=False, is_flag=True, show_envvar=True,
              help="Display current run progression")
@click.option("-P", "--pause", "pause",
              default=None, is_flag=True, show_envvar=True,
              help="Pause the current run")
@click.option("-R", "--resume", "resume",
              default=None, is_flag=True, show_envvar=True,
              help="Resume a previously paused run")
@click.option("-b", "--bootstrap", "bootstrap",
              default=False, is_flag=True, show_envvar=True,
              help="Initialize basic test templates in given directory")
@click.option("-f", "--override", "override",
              default=False, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output directory")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
def run(ctx, profilename, output, detach, status, resume, pause, bootstrap, override, set_default, dirs) -> None:
    """
    Execute a validation suite from a given PROFILE.

    By default the current directory is scanned to find test-suites to run.
    May also be provided as a list of directories as described by tests
    found in LIST_OF_DIRS.
    """
    # parse non-run situations
    if bootstrap:
        log.info("Bootstrapping directories")
        log.nimpl("Bootstrap")
        exit(0)
    elif pause and resume:
        log.err("Cannot pause and resume the run at the same time!", abort=1)
    elif pause:
        log.nimpl("pause")
        exit(0)
    elif resume:
        log.nimpl("resume")
        exit(0)
    elif status:
        log.nimpl("status")
        exit(0)
    elif set_default:
        log.nimpl("set_defaults")
        #io.open_in_editor("defaults")
        exit(0)

    # fill validation run_setttings
    run_setttings = {}
    # for any 'None' value, a load from default should be made
    run_setttings['verbose'] = ctx.obj['verbose']
    run_setttings['color'] = ctx.obj['color']
    run_setttings['pfname'] = profilename
    run_setttings['output'] = os.path.join(os.path.abspath(output), ".pcvs")
    #run_setttings['tee'] = log
    run_setttings['bg'] = detach
    run_setttings['force'] = override

    (scope, label) = pvProfile.extract_profile_from_token(profilename)
    pf = pvProfile.Profile(label, scope)
    if not pf.is_found():
        log.err("Please use a valid profile name:",
                "No '{}' found!".format(profilename), abort=1)
    else:
        pf.load_from_disk()
    log.banner()
    log.print_header("Prepare Environment")
    pvRun.prepare(run_setttings, dirs, pf)

    log.print_header("Process benchmarks")
    start = time.time()
    pvRun.process()
    log.print_section("===> Processing done in {:<.3f} sec(s)".format(time.time() - start))
    
    log.print_header("Validation Start")
    pvRun.run()

    log.print_header("Finalization")
    pvRun.terminate()
