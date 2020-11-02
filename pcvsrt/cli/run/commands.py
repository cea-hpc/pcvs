import os
import time
from typing import Optional
import click
import yaml
import pprint
from datetime import datetime

from yaml.loader import Loader

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
            raise click.BadArgumentUsage("\n".join([
                    "While parsing user directories:",
                    '{}'.format(err_msg),
                    "please see '--help' for more information"
                ]))
    return list_of_dirs


def compl_list_dirs(ctx, args, incomplete) -> list:  # pragma: no cover
    abspath = os.path.abspath(incomplete)
    
    if ':' in incomplete:
        pass
    else:
        pass
    d = os.path.dirname(abspath)
    base = os.path.basename(abspath)
    return ['a' for p in next(os.walk(d))[1] if p.startswith(base)]


@click.command(name="run", short_help="Run a validation")
@click.option("-p", "--profile", "profilename", default="default",
              autocompletion=cmdProfile.compl_list_token,
              type=str, show_envvar=True, help="an existing profile")
@click.option("-o", "--output", "output", default=None, show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="Where artefacts will be stored during/after the run")
@click.option("-e", "--edit", "set_default",
              default=None, is_flag=True,
              help="Set default values for run options (WIP)")
@click.option("-s", '--validation', "validation_file",
              default=None, show_envvar=True, type=str,
              help="Validation settings file")
@click.option("-l/-L", "--tee/--no-tee", "tee", show_envvar=True,
              default=None, is_flag=True,
              help="Log the whole stdout/stderr")
@click.option("--detach", "detach",
              default=True, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously (WIP)")
@click.option("--status", "status",
              default=False, is_flag=True, show_envvar=True,
              help="Display current run progression")
@click.option("-P", "--pause", "pause",
              default=None, is_flag=True, show_envvar=True,
              help="Pause the current run [TBD]")
@click.option("-R", "--resume", "resume",
              default=None, is_flag=True, show_envvar=True,
              help="Resume a previously paused run [TBD]")
@click.option("-B", "--bootstrap", "bootstrap",
              default=False, is_flag=True, show_envvar=True,
              help="Initialize basic test templates in given directory [TBD]")
@click.option("-f", "--override", "override",
              default=False, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output directory")
@click.option("-d", "--dry-run", "simulated",
              default=None, is_flag=True,
              help="Reproduce the whole process without actually running tests")
@click.option("-a", "--anonymize", "anon",
              default=None, is_flag=True,
              help="Purge final archive from sensitive data (HOME, USER...)")
@click.option("-b", "--bank", "bank",
              default=None, 
              help="Which bank will store data instead of creating an archive")
@click.option("--duplicate", "dup", default=None,
              type=click.Path(exists=True, file_okay=False), required=False,
              help="Reuse previously loaded path(s) (ignores any DIRS argument")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
def run(ctx, profilename, output, detach, status, resume, pause, bootstrap,
        override, tee, anon, validation_file, simulated, bank, dup,
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
        raise click.BadOptionUsage("Cannot pause and resume the run at the same time!")
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
        io.open_in_editor(system.CfgValidation.get_valfile(validation_file))
        exit(0)

    theBank = None
    if bank is not None:
        theBank = pvBank.Bank(bank)
        if not theBank.exists():
            log.err('--bank points to a non-existent bank')
    
    # fill validation run_setttings
    settings = system.Settings()
    cfg_val = system.CfgValidation(validation_file)
    cfg_val.override('datetime', datetime.now())
    cfg_val.override('verbose', ctx.obj['verbose'])
    cfg_val.override('color', ctx.obj['color'])
    cfg_val.override('output', output)
    cfg_val.override('background', detach)
    cfg_val.override('override', override)
    cfg_val.override('dirs', dirs)
    cfg_val.override('simulated', simulated)
    cfg_val.override('anonymize', anon)
    cfg_val.override('exported_to', bank)
    cfg_val.override('tee', tee)
    
    if dup is not None:
        try:
            settings = pvRun.dup_another_build(dup, cfg_val.output)
            #TODO: for now, none of the CLI options overrides duplicated build
            # except 'output'
        except FileNotFoundError:
            raise click.BadOptionUsage("--duplicate", "{} is not a valid build directory!".format(dup))
    else:
        (scope, label) = pvProfile.extract_profile_from_token(profilename)
        pf = pvProfile.Profile(label, scope)
        if not pf.is_found():
            log.err("Please use a valid profile name:",
                    "No '{}' found!".format(profilename))
        pf.load_from_disk()
        cfg_val.override('pf_name', pf.full_name)
        settings.runtime = system.CfgRuntime(pf.runtime)
        settings.compiler = system.CfgCompiler(pf.compiler)
        settings.machine = system.CfgMachine(pf.machine)
        settings.criterion = system.CfgCriterion(pf.criterion)
        settings.group = system.CfgTemplate(pf.group)
        settings.validation = cfg_val

    system.save_as_global(settings)

    if system.get('validation').tee:
        log.init_tee(system.get('validation').output)

    log.banner()
    log.print_header("Prepare Environment")
    pvRun.prepare(settings, dup is not None)

    log.print_header("Process benchmarks")
    if dup:
        log.print_section("Reusing previously generated inputs")
        log.print_section("Duplicated from {}".format(os.path.abspath(dup)))
    else:
        start = time.time()
        pvRun.process()
        log.print_section("===> Processing done in {:<.3f} sec(s)".format(time.time() - start))
    
    log.print_header("Validation Start")
    pvRun.run()

    log.print_header("Finalization")
    archive = pvRun.terminate()

    if theBank is not None:
        theBank.save(
            system.get('validation').datetime.strftime('%Y-%m-%d'),
            os.path.join(system.get('validation').output, archive)
        )
