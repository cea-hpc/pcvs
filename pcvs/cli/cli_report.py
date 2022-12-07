import os

from pcvs import NAME_BUILDFILE
from pcvs import NAME_BUILDIR
from pcvs import io
from pcvs.backend import report as pvReport
from pcvs.helpers import log

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click


@click.command('report', short_help="Manage PCVS result reporting interface")
@click.option("-s", "--static-pages", "static", flag_value=".", default=None)
@click.argument("path_list", nargs=-1, required=False, type=click.Path(exists=True))
@click.pass_context
def report(ctx, path_list, static):
    """Start a webserver to browse result during or after execution.

    Listens by default to http://localhost:5000/"""
    inputs = list()
    # sanity check
    for prefix in path_list:
        # if a dir is given BU does not point to a valid build dir,
        # attempt to resolve it.
        # Note that files are always kept, it ensure to the user to
        # provide a valid archive-formatted file
        print(prefix)
        if not os.path.isfile(prefix) and \
                not os.path.isfile(os.path.join(prefix, NAME_BUILDFILE)):
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
                if os.path.isfile(prefix):
                    pvReport.upload_buildir_results_from_archive(prefix)
                else:
                    pvReport.upload_buildir_results(prefix)
            except Exception as e:
                io.console.warn("Unable to parse {}".format(prefix))
                io.console.debug("Caught {}".format(e))
                raise e
        # create the app
        pvReport.start_server()
