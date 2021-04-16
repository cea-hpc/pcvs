import os
import time
from datetime import datetime

import click
import yaml

from pcvs import PATH_SESSION
from pcvs.backend import bank as pvBank
from pcvs.backend import profile as pvProfile
from pcvs.backend import run as pvRun
from pcvs.backend import session as pvSession
from pcvs.cli import cli_bank, cli_profile
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
@click.option("--detach", "detach",
              default=False, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously (WIP)")
@click.option("-f/-F", "--override/--no-override", "override",
              default=False, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output directory")
@click.option("-d", "--dry-run", "simulated",
              default=None, is_flag=True,
              help="Reproduce the whole process without running tests")
@click.option("-a", "--anonymize", "anon",
              default=None, is_flag=True,
              help="Purge the results from sensitive data (HOME, USER...)")
@click.option("-b", "--bank", "bank", default=None, autocompletion=cli_bank.compl_bank_projects,
              help="Which bank will store the run in addition to the archive")
@click.option("--duplicate", "dup", default=None,
              type=click.Path(exists=True, file_okay=False), required=False,
              help="Reuse old test directories (no DIRS required)")
@click.argument("dirs", nargs=-1,
                type=str, callback=iterate_dirs)
@click.pass_context
def run(ctx, profilename, output, detach, override, anon, validation_file,
        simulated, bank, dup, set_default, dirs) -> None:
    """
    Execute a validation suite from a given PROFILE.

    By default the current directory is scanned to find test-suites to run.
    May also be provided as a list of directories as described by tests
    found in LIST_OF_DIRS.
    """
    if set_default:
        utils.open_in_editor(system.MetaConfig.validation_default_file)
        exit(0)

    # first, prepare raw arguments to be usable
    if output is not None:
        output = os.path.abspath(output)

    if bank is not None:
        obj = pvBank.Bank(token=bank, path=None)
        if not obj.exists():
            click.BadOptionUsage("--bank", "'{}' bank does not exist".format(obj.name))

    global_config = system.MetaConfig()        

    # then init the configuration
    val_cfg = global_config.bootstrap_validation_from_file(validation_file)

    # save 'run' parameters into global configuration
    val_cfg.set_ifdef('datetime', datetime.now())
    val_cfg.set_ifdef('verbose', ctx.obj['verbose'])
    val_cfg.set_ifdef('color', ctx.obj['color'])
    val_cfg.set_ifdef('output', output)
    val_cfg.set_ifdef('background', detach)
    val_cfg.set_ifdef('override', override)
    val_cfg.set_ifdef('dirs', dirs)
    val_cfg.set_ifdef('simulated', simulated)
    val_cfg.set_ifdef('anonymize', anon)
    val_cfg.set_ifdef('reused_build', dup)
    val_cfg.set_ifdef('target_bank', bank)
    
    # check if another build should reused
    # this avoids to re-run combinatorial system twice
    if dup is not None:
        try:
            global_config = pvRun.dup_another_build(dup, val_cfg.output)
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
            raise click.BadOptionUsage(
                "--profile", "Profile '{}' not found".format(profilename))
        pf.load_from_disk()

        val_cfg.set_ifdef('pf_name', pf.full_name)
        val_cfg.set_ifdef('pf_hash', pf.get_unique_id())
        global_config.bootstrap_compiler(pf.compiler)
        global_config.bootstrap_runtime(pf.runtime)
        global_config.bootstrap_machine(pf.machine)
        global_config.bootstrap_criterion(pf.criterion)
        global_config.bootstrap_group(pf.group)

    system.MetaConfig.root = global_config

    the_session = pvSession.Session(val_cfg.datetime, val_cfg.output)
    the_session.register_callback(callback=pvRun.process_main_workflow,
                                  io_file=os.path.join(
                                            global_config.validation.output,
                                            'out.log'
                                          ))
    if detach:
        sid = the_session.run_detached(the_session)
        log.manager.print_item("Session successfully started, ID {}".format(sid))
    else:
        the_session.run(the_session)
