#!/usr/bin/env python3

import os

import click
import pkg_resources

from pcvsrt import config, globals, logs, profile

from .config import commands as cmdConfig
from .profile import commands as cmdProfile
from .run import commands as cmdRun


CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help', '-help'],
    ignore_unknown_options=True,
    allow_interspersed_args=False,
    auto_envvar_prefix='PCVS',
    show_default=True
)


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    version = pkg_resources.require("pcvs-rt")[0].version
    click.echo('PCVS Runtime Tool (pcvs-rt) -- version {}'.format(version))
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
@click.option("-w", "--width", "width", type=int, default=0,
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

    logs.init(verbose, encoding)
    globals.set_exec_path(ctx.obj['exec'])
    globals.LINELENGTH, _ = click.get_terminal_size()

    # detections
    config.init()
    profile.init()


@cli.command(
    "help",
    short_help="Quick Guide to prepare PCVS after a fresh installation")
@click.argument("category", nargs=1, required=False, default=None,
                type=click.Choice(['completion', 'config', 'scope', 'token']))
@click.pass_context
def cli_doc(ctx, category):

    logs.print_header("Documentation")

    logs.print_section("Enable completion (cmds to be run or added to ~/.*rc)")
    for shell in ['zsh', 'bash']:
        logs.print_item(
            "{: >4s}: eval \"$(_PCVS_COMPLETE=source_{} pcvs)\"".
            format(shell.upper(), shell))
    pass

    logs.print_section("Create basic configuration blocks")
    logs.print_item("WIP")

    logs.print_section("Create a profile")
    logs.print_item("WIP")

    logs.print_section("Make a compliant test-suite")
    logs.print_item("WIP")

    logs.print_section("Run a  simple validation")
    logs.print_item("WIP")

    logs.print_section("Browse results")
    logs.print_item("WIP")


cli.add_command(cmdConfig.config)
cli.add_command(cmdProfile.profile)
cli.add_command(cmdRun.run)
