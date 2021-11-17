#!/usr/bin/env python3

import os
import shutil

import click

from pcvs import version
from pcvs.backend import bank, config, profile, session
from pcvs.cli import (cli_bank, cli_config, cli_profile, cli_report, cli_run,
                      cli_session, cli_utilities)
from pcvs.helpers import log, utils
from pcvs.helpers.exceptions import PluginException
from pcvs.plugins import Collection, Plugin

CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help', '-help'],
    ignore_unknown_options=True,
    allow_interspersed_args=False,
    auto_envvar_prefix='PCVS'
)


def print_version(ctx, param, value):
    """Print current version.

    This is used as an option formatter, PCVS is not event loaded yet.

    :param ctx: Click Context.
    :type ctx: :class:`Click.Context`
    :param param: the option triggering the callback (unused here)
    :type param: str
    :param value: the value provided with the option (unused here)
    """
    if not value or ctx.resilient_parsing:
        return
    click.echo(
        'Parallel Computing Validation System (pcvs) -- version {}'.format(version.__version__))
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
@click.option("-P", "--plugin-path", "plugin_path", multiple=True,
              type=click.Path(exists=True), show_envvar=True,
              help="Default Plugin path prefix")
@click.option("-m", "--plugin", "select_plugins", multiple=True)
@click.pass_context
@log.manager.capture_exception(PluginException.NotFoundError)
def cli(ctx, verbose, color, encoding, exec_path, width, plugin_path, select_plugins):
    """PCVS main program."""
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

    utils.create_home_dir()

    pcoll = Collection()
    ctx.obj['plugins'] = pcoll

    pcoll.register_default_plugins()

    if plugin_path:
        for path in plugin_path:
            pcoll.register_plugin_by_dir(path)

    for arg in select_plugins:
        for select in arg.split(','):
            pcoll.activate_plugin(select)

    pcoll.invoke_plugins(Plugin.Step.START_BEFORE)

    # detections
    config.init()
    profile.init()
    bank.init()

    pcoll.invoke_plugins(Plugin.Step.START_AFTER)


cli.add_command(cli_config.config)
cli.add_command(cli_profile.profile)
cli.add_command(cli_run.run)
cli.add_command(cli_bank.bank)
cli.add_command(cli_session.session)
cli.add_command(cli_utilities.exec)
cli.add_command(cli_utilities.check)
cli.add_command(cli_utilities.clean)
cli.add_command(cli_utilities.discover)
# cli.add_command(cli_gui.gui)
cli.add_command(cli_report.report)

if __name__ == "__main__":
    cli()
