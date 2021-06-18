import os

import click

from pcvs import NAME_BUILDFILE, NAME_BUILDIR
from pcvs.backend import report as pvReport


@click.command('report', short_help="Manage PCVS result reporting interface")
@click.option("-s", "--static-pages", "static", flag_value=".", default=None)
@click.argument("path_list", nargs=-1, required=False)
@click.pass_context
def report(ctx, path_list, static):
    inputs = list()
    if len(path_list) == 0:
        inputs.append(os.path.join(os.getcwd(), NAME_BUILDIR))

    # sanity check
    for prefix in path_list:
        if not os.path.isfile(os.path.join(prefix, NAME_BUILDFILE)):
            raise click.BadArgumentUsage('{} is not a build directory.'.format(prefix))
        inputs.append(os.path.abspath(prefix))

    if static:
        # server old-style JCRHONOSS pages after JSON transformation
        for prefix in inputs:
            pvReport.build_static_pages(prefix)
    else:
        # feed with prefixes
        for prefix in inputs:
            pvReport.upload_buildir_results(prefix)
        # create the app
        pvReport.start_server()
