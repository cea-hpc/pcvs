#!/usr/bin/env python3

import click

from .config import commands as cmdConfig
from .profile import commands as cmdProfile
from .run import commands as cmdRun

from pcvsrt.utils import logs


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo("WARNING: Version number should be updated dynamically when installing!")
    click.echo('PCVS Runtime Tool (pcvs-rt) -- version {}'.format('0.6.0'))
    ctx.exit()

CONTEXT_SETTINGS = dict(
                        help_option_names=['-h', '--help', '-help'],
                        ignore_unknown_options=True,
                        allow_interspersed_args=False,
                        terminal_width=logs.LINELENGTH,
                        auto_envvar_prefix='PCVS',
                        show_default=True
                        )


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
@click.option("-V", "--version", expose_value=False, is_eager=True, callback=print_version, is_flag=True)
@click.pass_context
def cli(ctx, verbose, color, encoding):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['color'] = color
    ctx.obj['encode'] = encoding

    logs.init(verbose, color, encoding)


@cli.command("doc",
             short_help="Quick Guide to prepare PCVS after a fresh installation")
@click.argument("category", type=click.Choice(['completion', 'config', 'scope', 'token']), nargs=1, required=False, default=None)
@click.pass_context
def cli_doc(ctx, category):
    
    logs.print_header("Documentation")

    logs.print_section("Enable completion (cmds to be run or added to ~/.*rc)")
    for shell in ['zsh', 'bash']:
        logs.print_item("{: >4s}: eval \"$(_PCVS_COMPLETE=source_{} pcvs)\"".format(shell.upper(), shell))
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
