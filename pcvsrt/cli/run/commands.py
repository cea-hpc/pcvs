import os
import time
import click
import yaml
import pprint

from pcvsrt.helpers import io, log, system
from pcvsrt.cli.run import backend as pvRun
from pcvsrt.cli.profile import backend as pvProfile
from pcvsrt.cli.bank import backend as pvBank

from pcvsrt.cli.profile import commands as cmdProfile


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
@click.option("-o", "--output", "output", default=None, show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="Where artefacts will be stored during/after the run")
@click.option("-c", "--set-defaults", "set_default",
              default=None, is_flag=True,
              help="Set default values for run options (WIP)")
@click.option("-s", '--validation', "validation_file",
              default=None, show_envvar=True, type=str,
              help="Validation settings file")
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
@click.option("-d", "--dry-run", "simulated",
             default=None, is_flag=True,
             help="Reproduce the whole process without actually running tests")
@click.option("-a", "--anonymize", "anon",
              default=None, is_flag=True,
              help="Purge final archive from sensitive data (HOME, USER...)")
@click.option("-e", "--export", "export",
              default=None, 
              help="Which bank will store data instead of creating an archive")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
def run(ctx, profilename, output, detach, status, resume, pause, bootstrap,
            override, anon, validation_file, simulated, export,
            set_default, dirs) -> None:
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
    settings = system.Settings()

    cfg_val = system.CfgValidation(validation_file)

    cfg_val.override('verbose', ctx.obj['verbose'])
    cfg_val.override('color', ctx.obj['color'])
    cfg_val.override('output', output)
    cfg_val.override('background', detach)
    cfg_val.override('override', override)
    cfg_val.override('dirs', dirs)
    cfg_val.override('simulated', simulated)
    cfg_val.override('anonymize', anon)
    cfg_val.override('exported_to', export)

    (scope, label) = pvProfile.extract_profile_from_token(profilename)
    
    pf = pvProfile.Profile(label, scope)
    cfg_val.override('pf_name', pf.full_name)
    
    if not pf.is_found():
        log.err("Please use a valid profile name:",
                "No '{}' found!".format(profilename), abort=1)
    else:
        pf.load_from_disk()
        
        settings.runtime = system.CfgRuntime(pf.runtime)
        settings.compiler = system.CfgCompiler(pf.compiler)
        settings.machine = system.CfgMachine(pf.machine)
        settings.criterion = system.CfgCriterion(pf.criterion)
        settings.group = system.CfgTemplate(pf.group)

    settings.dirs = dirs
    settings.validation = cfg_val

    system.save_as_global(settings)
    log.banner()
    log.print_header("Prepare Environment")
    pvRun.prepare(settings)

    log.print_header("Process benchmarks")
    start = time.time()
    pvRun.process()
    log.print_section("===> Processing done in {:<.3f} sec(s)".format(time.time() - start))
    
    log.print_header("Validation Start")
    pvRun.run()

    log.print_header("Finalization")
    pvRun.terminate()
