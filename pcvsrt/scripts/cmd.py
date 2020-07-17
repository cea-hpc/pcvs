#!/usr/bin/env python3

import click

from .config import commands as cmdConfig
from .profile import commands as cmdProfile
from .run import commands as cmdRun

from pcvsrt.utils import logs


CONTEXT_SETTINGS = dict(
                        help_option_names=['-h', '--help'],
                        ignore_unknown_options=True,
                        allow_interspersed_args=False
                        )


@click.group(context_settings=CONTEXT_SETTINGS, name="cli")
@click.option("-v", "--verbose", "verbose",
              count=True, default=0,
              help="Verbosity (cumulative)")
@click.option("-c/-C", "--color/--no-color", "color",
              default=True, is_flag=True,
              help="Use colors to beautify the output")
@click.option("-u/-U", "--unicode/--no-unicode", "encoding",
              default=True, is_flag=True,
              help="enable/disable Unicode glyphs")
@click.pass_context
def cli(ctx, verbose, color, encoding):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['color'] = color
    ctx.obj['encode'] = encoding

    logs.init(verbose, color, encoding)


cli.add_command(cmdConfig.config)
cli.add_command(cmdProfile.profile)
cli.add_command(cmdRun.run)
