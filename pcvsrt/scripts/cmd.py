#!/usr/bin/env python3

import click

from .config import commands as cmdConfig
from .profile import commands as cmdProfile
from .run import commands as cmdRun

@click.group(name="cli")
@click.pass_context
def cli(ctx):
    pass


cli.add_command(cmdConfig.config)
cli.add_command(cmdProfile.profile)
cli.add_command(cmdRun.run)


if __name__ == '__main__':
    try:
        cli()
    except click.FileError:
        pass
    except click.NoSuchOption:
        pass
    except click.BadOptionUsage:
        pass
    except click.BadArgumentUsage:
        pass
    except click.UsageError:
        pass
    except click.ClickException:
        pass
    else:
        pass
