import os

import click

from pcvs import NAME_BUILDFILE, NAME_BUILDIR
from pcvs.backend import report as pvReport


@click.command('report', short_help="Manage PCVS result reporting interface")
@click.option('-w', '--web', 'mode', flag_value='web', default=True,
              help="Generate web-based GUI")
@click.argument("path", required=False, default=None)
@click.pass_context
def report(ctx, mode, path):
    inputs = list()
    if path is None:
        path = os.path.join(os.getcwd(), NAME_BUILDIR)

    if not os.path.isfile(os.path.join(path, NAME_BUILDFILE)):
        click.BadArgumentUsage('{} is not a build directory.'.format(path))

    path = os.path.join(path, 'rawdata')

    if mode == "web":
        pvReport.webview_run_server(path)
