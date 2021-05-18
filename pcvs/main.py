#!/usr/bin/env python3

import os
import shutil
import click
import pkg_resources

from pcvs.backend import bank, config, profile, session
from pcvs.cli import (cli_bank, cli_config, cli_profile, cli_report, cli_run,
                      cli_session, cli_utilities)
from pcvs.helpers import log, utils
from pcvs import version

CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help', '-help'],
    ignore_unknown_options=True,
    allow_interspersed_args=False,
    auto_envvar_prefix='PCVS'
)


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('Parallel Computing Validation System (pcvs) -- version {}'.format(version.__version__))
    ctx.exit()


@click.group(context_settings=CONTEXT_SETTINGS, name="cli")
@click.option("-v", "--verbose", "verbose", show_envvar=True,
              count=True, default=0,
              help="Verbosity (cumulative)")
@click.option("-c", "--color/--no-color", "color",
              default=True, is_flag=True, show_envvar=True,
              help="Use colors to beautify the output")
@click.option("-g", "--glyph/--no-glyph", "encoding",
              default=True, is_flag=True, show_envvar=True,
              help="enable/disable Unicode glyphs")
@click.option("-C", "--exec-path", "exec_path", show_envvar=True,
              default=".", type=click.Path(exists=True, file_okay=False))
@click.option("-V", "--version",
              expose_value=False, is_eager=True, callback=print_version,
              is_flag=True, help="Display current version")
@click.option("-w", "--width", "width", type=int, default=None,
              help="Terminal width (autodetection if omitted")
@click.pass_context
def cli(ctx, verbose, color, encoding, exec_path, width):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['color'] = color
    ctx.obj['encode'] = encoding
    ctx.obj['exec'] = os.path.abspath(exec_path)

    # Click specific-related
    ctx.color = color

    if width is None:
        width = shutil.get_terminal_size()[0]
    log.init(verbose, encoding, width)
    utils.set_local_path(ctx.obj['exec'])

    # detections
    config.init()
    profile.init()
    bank.init()


@cli.command(
    "help",
    short_help="Quick Guide to prepare PCVS after a fresh installation")
@click.argument("category", nargs=1, required=False, default=None,
                type=click.Choice(['completion', 'config', 'scope', 'token']))
@click.pass_context
def cli_doc(ctx, category):

    log.manager.print_header("Documentation")

    log.manager.print_section("Enable completion (cmds to be run or added to ~/.*rc)")
    for shell in ['zsh', 'bash']:
        log.manager.print_item(
            "{: >4s}: eval \"$(_PCVS_COMPLETE=source_{} pcvs)\"".
            format(shell.upper(), shell))
    pass

    log.manager.print_section("Create basic configuration blocks")
    log.manager.print_item("WIP")

    log.manager.print_section("Create a profile")
    log.manager.print_item("WIP")

    log.manager.print_section("Make a compliant test-suite")
    log.manager.print_item("WIP")

    log.manager.print_section("Run a  simple validation")
    log.manager.print_item("WIP")

    log.manager.print_section("Browse results")
    log.manager.print_item("WIP")


cli.add_command(cli_config.config)
cli.add_command(cli_profile.profile)
cli.add_command(cli_run.run)
cli.add_command(cli_bank.bank)
cli.add_command(cli_session.session)
cli.add_command(cli_utilities.exec)
cli.add_command(cli_utilities.check)
cli.add_command(cli_utilities.clean)
cli.add_command(cli_utilities.discover)
#cli.add_command(cli_gui.gui)
cli.add_command(cli_report.report)

if __name__ == "__main__":
    cli()
