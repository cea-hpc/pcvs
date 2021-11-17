import os

import click

from pcvs import NAME_BUILDFILE, NAME_BUILDIR
from pcvs.backend import report as pvReport
from pcvs.helpers import log


@click.command('report', short_help="Manage PCVS result reporting interface")
@click.option("-s", "--static-pages", "static", flag_value=".", default=None)
@click.argument("path_list", nargs=-1, required=False)
@click.pass_context
def report(ctx, path_list, static):
    """Start a webserver to browse result during or after execution.

    Listens by default to http://localhost:5000/"""
    inputs = list()
    # sanity check
    for prefix in path_list:
        # if given prefix does not point to a valid build directory
        if not os.path.isfile(os.path.join(prefix, NAME_BUILDFILE)):
            # if the 'builddir' default name was missing for resolution, add it
            if os.path.isfile(os.path.join(prefix, NAME_BUILDIR, NAME_BUILDFILE)):
                prefix = os.path.join(prefix, NAME_BUILDIR)
            else:  # otherwise, it is a wrong path -> error
                raise click.BadArgumentUsage(
                    '{} is not a build directory.'.format(prefix))

        inputs.append(os.path.abspath(prefix))

    # extra step, if the user didn't specify anything, attempt to add cwd
    current_dir = os.path.join(os.getcwd(), NAME_BUILDIR)
    if len(inputs) == 0 and os.path.isfile(os.path.join(current_dir, NAME_BUILDFILE)):
        inputs.append(current_dir)

    if static:
        # server old-style JCRHONOSS pages after JSON transformation
        for prefix in inputs:
            pvReport.build_static_pages(prefix)
    else:
        # feed with prefixes
        for prefix in inputs:
            try:
                pvReport.upload_buildir_results(prefix)
            except Exception as e:
                log.manager.warn("Unable to parse {}".format(prefix))
                log.manager.debug("Caught {}".format(e))
        # create the app
        pvReport.start_server()
