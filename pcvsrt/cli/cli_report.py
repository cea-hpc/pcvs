import os
from pcvsrt import BUILD_NAMEDIR

import click

from pcvsrt.backend import report as pvReport
from pcvsrt.helpers import log


@click.command('report', short_help="Manage PCVS result reporting interface")
@click.option('-w', '--web', 'mode', flag_value='web', default=True,
              help="Generate web-based GUI")
@click.argument("path", required=False, default=None)
@click.pass_context
def report(ctx, mode, path):
    inputs = list()
    if path is None:
        path = os.path.join(os.getcwd(), BUILD_NAMEDIR)

    if not os.path.isfile(os.path.join(path, BUILD_IDFILE)):
        log.err('{} is not a build directory. Abort.'.format(path))

    path = os.path.join(path, 'test_suite')

    for root, _ , files in os.walk(path):
        for f in files:
            if f.startswith('output-') and f.endswith('-list_of_tests.xml.json'):
                inputs.append(os.path.join(root, f))

    if mode == "web":
        pvReport.run_webserver(path)
