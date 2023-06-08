import os

from pcvs import NAME_BUILDFILE, NAME_BUILDIR, io
from pcvs.backend import report as pvReport
#from pcvs.gui.curses import viewer
from pcvs.helpers import utils

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
    if not path_list:
        path_list = [os.getcwd()]

    inputs = list()
    for prefix in path_list:
        # if a dir is given BU does not point to a valid build dir,
        # attempt to resolve it.
        # Note that files are always kept, it ensure to the user to
        # provide a valid archive-formatted file
        if utils.check_is_build_or_archive(prefix):
            inputs.append(os.path.abspath(prefix))
        elif utils.check_is_build_or_archive(os.path.join(prefix, NAME_BUILDIR)):
            inputs.append(os.path.abspath(os.path.join(prefix, NAME_BUILDIR)))
        else:
            raise click.BadArgumentUsage(
                '{} is not a build directory.'.format(prefix))

    if static:
        # server old-style JCRHONOSS pages after JSON transformation
        for prefix in inputs:
            pvReport.build_static_pages(prefix)
    else:
        # feed with prefixes
        r = pvReport.Report()
        for prefix in inputs:
            try:
                r.add_session(prefix)
            except Exception as e:
                io.console.warn("Unable to parse {}".format(prefix))
                io.console.debug("Caught {}".format(e))
                raise e
        # create the app
        pvReport.start_server(r)
