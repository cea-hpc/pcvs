import base64
import copy
import os
import shutil
import subprocess
import sys
from datetime import datetime

from rich.panel import Panel
from rich.table import Table

from pcvs import NAME_BUILDFILE
from pcvs import io
from pcvs.backend import utilities as pvUtils
from pcvs.helpers.system import MetaConfig

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click


@click.command(name="exec", short_help="Running aspecific test")
@click.option('-o', '--output', 'output', default=None,
              help="Directory where build artifacts are stored")
@click.option('-l', '--list', 'gen_list', is_flag=True,
              help='List available tests (may take a while)')
@click.option("-s", "--show", "display",
              type=click.Choice(['cmd', 'env', 'loads', 'all', 'out']), default=None,
              is_flag=False, flag_value="all",
              help="Display information instead of executing the command")
@click.argument("argument", type=str, required=False)
@click.pass_context
def exec(ctx, output, argument, gen_list, display) -> None:
    """ Run a unit test as it would have been through the whole engine (for
    reproducing purposes) from the command line."""
    rc = 0
    err = subprocess.STDOUT
    env = copy.deepcopy(os.environ)

    if display == 'out':
        # special case
        print(pvUtils.get_logged_output(output, argument))
        return

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
                ['bash', f, argument],
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
    io.console.print_banner()
    errors = dict()
    if color:
        display = Panel.fit("\n".join([
            "[red bold]Color[/], [i]Styles[/] & [underline]encoding[/] are managed by [cyan bold]Rich[/].",
            "[green bold]Please[/] visit their project: https://github.com/Textualize/rich",
            ":warning: To [underline]disable[/] [dim]Markups & Highlighting support[/]",
            "please use `--no-color` to the [red blink]PCVS[/] root command."
        ]))
        io.console.print(display)
        return

    if encoding:
        t = Table("Alias", "Symbol", "Fallback", title="UTF Support")
        w = io.SpecialChar(utf_support=True)
        wo = io.SpecialChar(utf_support=False)
        for k in io.SpecialChar.__dict__.keys():
            if k.startswith("_"):
                continue
            t.add_row(k, str(getattr(w, k)), str(getattr(wo, k)))
        io.console.print(t)
        return

    if configs:
        io.console.print_header("Configurations")
        errors = {**errors, **pvUtils.process_check_configs()}

    if profiles:
        io.console.print_header("Profile(s)")
        errors = {**errors, **pvUtils.process_check_profiles()}

    if dir:
        io.console.print_header("Test directories")
        io.console.print_section("Prepare the environment")
        # first, replace build dir with a temp one
        settings = MetaConfig()
        cfg_val = settings.bootstrap_validation({})
        cfg_val.set_ifdef('output', "/tmp/test")
        errors = {**errors, **
                  pvUtils.process_check_directory(os.path.abspath(dir), pf_name)}

    table = Table("Count", "Type of error", title="Classification of errors", expand=True)
    if errors:
        for k, v in errors.items():
            table.add_row(str(v), base64.b64decode(k).decode('utf-8'))
        io.console.print(table)
    else:
        io.console.print("{succ} {cg} {succ}".format(
            succ=io.console.utf('succ'),
            cg="[green bold]Everything is OK![/]"
        ))


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
        io.console.warn(["IMPORTANT NOTICE:",
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

    io.console.print_header("DELETION")
    for path in paths:
        for root, dirs, files in os.walk(path):
            # current root need to be cleaned
            if NAME_BUILDFILE in files:
                io.console.print_section("Found build: {}".format(root))
                archives = [x for x in sorted(files) if x.startswith(
                    'pcvsrun_') and x.endswith('.tar.gz')]
                if len(archives) == 0 and fake:
                    io.console.print_item("No archive found.")
                else:
                    for f in archives:
                        arch_date = datetime.strptime(
                            f.replace('pcvsrun_', '').replace('.tar.gz', ''),
                            "%Y%m%d%H%M%S"
                        )
                        delta = datetime.now() - arch_date
                        if fake:
                            io.console.print_item('Age: {:>3} day(s): {}'.format(
                                delta.days, f))
                            continue
                        elif interactive:
                            if not click.confirm('{}: ({} days ago) ?'.format(f, delta.days)):
                                continue
                        os.remove(os.path.join(root, f))
                        io.console.print_item('Deleting {}'.format(f))
                if remove_build_dir:
                    if not fake:
                        if interactive:
                            if not click.confirm('{}: ?'.format(root)):
                                continue
                        shutil.rmtree(root)
                        io.console.print_item('Deleted {}'.format(root))

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
        io.console.print_section("{}".format(p))
        pvUtils.process_discover_directory(p, set, force)
