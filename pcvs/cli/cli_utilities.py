import base64
import copy
import os
import shutil
import subprocess
import sys
from datetime import datetime

import click
from prettytable import PrettyTable

from pcvs import NAME_BUILDFILE
from pcvs.backend import utilities as pvUtils
from pcvs.helpers import log
from pcvs.helpers.system import MetaConfig


@click.command(name="exec", short_help="Running aspecific test")
@click.option('-o', '--output', 'output', default=None,
              help="Directory where build artifacts are stored")
@click.option('-l', '--list', 'gen_list', is_flag=True,
              help='List available tests (may take a while)')
@click.option("-s", "--show", "display",
              type=click.Choice(['cmd', 'env', 'loads', 'all']), default=None,
              is_flag=False, flag_value="all",
              help="Display information instead of executing the command")
@click.argument("argument", type=str, required=False)
@click.pass_context
def exec(ctx, output, argument, gen_list, display):
    """ Run a unit test as it would have been through the whole engine (for
    reproducing purposes) from the command line."""
    rc = 0
    err = subprocess.STDOUT
    env = copy.deepcopy(os.environ)

    if display:
        env.update({'PCVS_SHOW': str(display)})

    if gen_list:
        script_path = pvUtils.locate_scriptpaths(output)
        argument = "--list"
        err = subprocess.DEVNULL
    else:
        if not argument:
            raise click.BadArgumentUsage("An argument is required")
        script_path = [
            pvUtils.compute_scriptpath_from_testname(argument, output)]
    try:
        for f in script_path:
            if not os.path.isfile(f):
                raise click.BadArgumentUsage(
                    "Launch script for '{}' not found".format(argument))
            fds = subprocess.Popen(
                ['sh', f, argument],
                env=env,
                stderr=err)
            fds.communicate()
            rc = fds.returncode
    except subprocess.CalledProcessError as e:
        rc = e.returncode

    # return code to console
    sys.exit(rc)


@click.command(name="check", short_help="Ensure future input will be conformant to standards")
@click.option("--encoding", "-E", "encoding", default=False, is_flag=True,
              help="Check capability to print utf-8 characters properly")
@click.option("--colouring", "-X", "color", default=False, is_flag=True,
              help="Check capability to print coloured characters properly")
@click.option("--directory", "-D", "dir", default=None,
              type=click.Path(exists=True, file_okay=False),
              help="Check correctness for pcvs.* files")
@click.option("--configs", "-C", "configs", default=False, is_flag=True,
              help="Check correctness for all registered configuation block")
@click.option("--profiles", "-P", "profiles", default=False, is_flag=True,
              help="Check correctness for all registered profiles")
@click.option("--profile-model", "-p", "pf_name", default="default",
              help="Custom profile to use when checking pcvs.setup scripts")
@click.pass_context
def check(ctx, dir, encoding, color, configs, profiles, pf_name):
    """Global input/output analyzer, validating configuration, profiles &
    terminal supports."""
    log.manager.print_banner()
    errors = dict()
    if color:
        log.manager.print_header("Colouring")
        t = PrettyTable()
        ctx.color = True
        t.field_names = ["Name", "Foreground", "Background"]
        for k in sorted(log.manager.color_list):
            t.add_row([k, click.style("Test", fg=k),
                      click.style("Test", bg=k)])
        print(t)

    if encoding:
        log.manager.print_header("Encoding")

        t = PrettyTable()
        t.field_names = ["Alias", "Symbol", "Fallback"]
        man_default = log.IOManager(0, False, 100, None, None)
        man_unicode = log.IOManager(0, True, 100, None, None)

        for k in sorted(man_default.avail_chars()):
            t.add_row([k, man_unicode.utf(k), man_default.utf(k)])
        print(t)

    if configs:
        log.manager.print_header("Configurations")
        errors = {**errors, **pvUtils.process_check_configs()}

    if profiles:
        log.manager.print_header("Profile(s)")
        errors = {**errors, **pvUtils.process_check_profiles()}

    if dir:
        log.manager.print_header("Test directories")
        log.manager.print_section("Prepare the environment")
        # first, replace build dir with a temp one
        settings = MetaConfig()
        cfg_val = settings.bootstrap_validation({})
        cfg_val.set_ifdef('output', "/tmp/test")
        errors = {**errors, **
                  pvUtils.process_check_directory(os.path.abspath(dir), pf_name)}

    if errors:
        log.manager.print_section("Classification of errors:")
        table = PrettyTable()
        table.field_names = ["Count", "Type of error"]

        for k, v in errors.items():
            table.add_row([v, base64.b64decode(k).decode('utf-8')])

        table.align["Count"] = "c"
        table.align["Type of error"] = "l"
        table.sortby = "Count"
        table.reversesort = True
        print(table)
    else:
        log.manager.print_section("{succ} {cg} {succ}".format(
            succ=log.manager.utf('succ'),
            cg=log.manager.style("Everything is OK!", fg='green', bold=True))
        )


@click.command(name="clean", short_help="Remove artifacts generated from PCVS")
@click.option("-f", "--force", "force", default=False, is_flag=True,
              help="Acknowledge there is no way back.")
@click.option("-d", "--dry-run", "fake", default=False, is_flag=True,
              help="Print artefacts instead of deleting them")
@click.option('-i', '--interactive', 'interactive',
              is_flag=True, default=False,
              help="Manage cleanup process interactively")
@click.option("--remove-dirs", "remove_build_dir", is_flag=True, default=False)
@click.argument("paths", required=False, type=click.Path(exists=True), nargs=-1)
@click.pass_context
def clean(ctx, force, fake, paths, remove_build_dir, interactive):
    """Find & clean workspaces from PCVS artifacts (build & archives)"""
    if not fake and not force:
        log.manager.warn(["IMPORTANT NOTICE:",
                          "This command will delete files from previous run(s) and",
                          "no recovery will be possible after deletion.",
                          "Please use --force to indicate you acknowledge the risks",
                          "and will face consequences in case of improper use.",
                          "",
                          "To list files to be deleted instead, you may use --dry-run."]
                         )
        sys.exit(0)
    if not paths:
        paths = [os.getcwd()]

    log.manager.print_header("DELETION")
    for path in paths:
        for root, dirs, files in os.walk(path):
            # current root need to be cleaned
            if NAME_BUILDFILE in files:
                log.manager.print_section("Found build: {}".format(root))
                archives = [x for x in sorted(files) if x.startswith(
                    'pcvsrun_') and x.endswith('.tar.gz')]
                if len(archives) == 0 and fake:
                    log.manager.print_item("No archive found.")
                else:
                    for f in archives:
                        arch_date = datetime.strptime(
                            f.replace('pcvsrun_', '').replace('.tar.gz', ''),
                            "%Y%m%d%H%M%S"
                        )
                        delta = datetime.now() - arch_date
                        if fake:
                            log.manager.print_item('Age: {:>3} day(s): {}'.format(
                                delta.days, f))
                            continue
                        elif interactive:
                            if not click.confirm('{}: ({} days ago) ?'.format(f, delta.days)):
                                continue
                        os.remove(os.path.join(root, f))
                        log.manager.print_item('Deleting {}'.format(f))
                if remove_build_dir:
                    if not fake:
                        if interactive:
                            if not click.confirm('{}: ?'.format(root)):
                                continue
                        shutil.rmtree(root)
                        log.manager.print_item('Deleted {}'.format(root))

                # stop the walk down to this top directory
                dirs[:] = []


@click.command(name="scan",
               short_help="Analyze directories to build up test conf. files")
@click.argument("paths", default=None, nargs=-1)
@click.option("-c/-l", "--create/--list", "set", is_flag=True, default=False)
@click.option("-f", "--force", "force", is_flag=True, default=False)
@click.pass_context
def discover(ctx, paths, set, force):
    """Discover & integrate new benchmarks to PCVS format."""
    if not paths:
        paths = [os.getcwd()]

    paths = [os.path.abspath(x) for x in paths]

    for p in paths:
        log.manager.print_section("{}".format(p))
        pvUtils.process_discover_directory(p, set, force)
