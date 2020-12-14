import os
import time
from datetime import datetime

import click

from pcvs.backend import bank as pvBank
from pcvs.backend import profile as pvProfile
from pcvs.backend import run as pvRun
from pcvs.cli import cli_profile
from pcvs.helpers import log, system, utils


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
              autocompletion=cli_profile.compl_list_token,
              type=str, show_envvar=True,
              help="Existing and valid profile supporting this run")
@click.option("-o", "--output", "output", default=None, show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="F directory where PCVS is allowed to store data")
@click.option("-e", "--edit", "set_default",
              default=None, is_flag=True,
              help="Edit default settings to run a validation")
@click.option("-s", '--validation', "validation_file",
              default=None, show_envvar=True, type=str,
              help="Define which setting file to use (~/.pcvs/validation.cfg)")
@click.option("-l/-L", "--tee/--no-tee", "tee", show_envvar=True,
              default=None, is_flag=True,
              help="Save stdout/stderr in a file in addition to terminal")
@click.option("--detach", "detach",
              default=True, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously (WIP)")
@click.option("--status", "status",
              default=False, is_flag=True, show_envvar=True,
              help="Display current run progression (WIP)")
@click.option("-P", "--pause", "pause",
              default=None, is_flag=True, show_envvar=True,
              help="Pause the current run (WIP)")
@click.option("-R", "--resume", "resume",
              default=None, is_flag=True, show_envvar=True,
              help="Resume a previously paused run (WIP)")
@click.option("-f/-F", "--override/--no-override", "override",
              default=False, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output directory")
@click.option("-d", "--dry-run", "simulated",
              default=None, is_flag=True,
              help="Reproduce the whole process without running tests")
@click.option("-a", "--anonymize", "anon",
              default=None, is_flag=True,
              help="Purge the results from sensitive data (HOME, USER...)")
@click.option("-b", "--bank", "bank",
              default=None, 
              help="Which bank will store data in addition to the archive")
@click.option("--duplicate", "dup", default=None,
              type=click.Path(exists=True, file_okay=False), required=False,
              help="Reuse old test directories (no DIRS required)")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
def run(ctx, profilename, output, detach, status, resume, pause,
        override, tee, anon, validation_file, simulated, bank, dup,
        set_default, dirs) -> None:
    """
    Execute a validation suite from a given PROFILE.

    By default the current directory is scanned to find test-suites to run.
    May also be provided as a list of directories as described by tests
    found in LIST_OF_DIRS.
    """
    # parse non-run situations
    if pause and resume:
        raise click.BadOptionUsage("--pause/--resume",
                "Cannot pause and resume the run at the same time!")
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
        utils.open_in_editor(system.CfgValidation.get_valfile(validation_file))
        exit(0)

    # appropriate bank election
    theBank = None
    if bank is not None:
        theBank = pvBank.Bank(bank)
        if not theBank.exists():
            log.err('--bank points to a non-existent bank')
    
    # save the whole run configuration
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
    cfg_val.override('target_bank', theBank)
    cfg_val.override('reused_build', dup)
    
    # check if another build should cloned
    # this avoids to re-run combinatorial system twice
    if dup is not None:
        try:
            settings = pvRun.dup_another_build(dup, cfg_val.output)
            #TODO: Currently nothing can be overriden from cloned build except:
            # - 'output'
        except FileNotFoundError:
            raise click.BadOptionUsage(
                "--duplicate", "{} is not a valid build directory!".format(dup))
    else:
        # otherwise create own settings command block
        (scope, _, label) = utils.extract_infos_from_token(profilename,
                                                           maxsplit=2)
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

    # save this commanb block as global.
    # any system.get(...) will use this block as root node
    system.save_as_global(settings)

    # from now, redirect stdout & stderr to the same logfile
    if system.get('validation').tee:
        log.init_tee(system.get('validation').output)

    log.banner()
    log.print_header("Prepare Environment")
    # prepare PCVS and third-party tools
    pvRun.prepare()

    log.print_header("Process benchmarks")
    if system.get('validation').reused_build is not None:
        log.print_section("Reusing previously generated inputs")
        log.print_section("Duplicated from {}".format(os.path.abspath(dup)))
    else:
        start = time.time()
        pvRun.process()
        end = time.time()
        log.print_section(
                "===> Processing done in {:<.3f} sec(s)".format(end-start))
    
    log.print_header("Validation Start")
    # real RUN !!
    pvRun.run()

    log.print_header("Finalization")
    # post-actions to build the archive, post-process the webview...
    archive = pvRun.terminate()

    if system.get('validation').target_bank:
        system.get('validation').target_bank.save(
            system.get('validation').datetime.strftime('%Y-%m-%d'),
            os.path.join(system.get('validation').output, archive)
        )
