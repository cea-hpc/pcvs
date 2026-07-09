import os

from pcvs import io
from pcvs import NAME_BUILDIR
from pcvs.backend import report as pvReport
from pcvs.helpers import utils
from pcvs.ui.textual import TEXTUAL_AVAIL
from pcvs.webview import start_server

try:
    import rich_click as click

    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click  # type: ignore


@click.command(
    "report",
    short_help="Manage PCVS result reporting interface",
)
@click.argument(
    "paths",
    nargs=-1,
    required=False,
    type=click.Path(exists=True),
    # help="The list of path to query for build folder/archive and add them to the report.",
)
@click.pass_context
def cli_report(ctx: click.Context, paths: tuple[str, ...]) -> int:
    """
    Start a webserver to browse result during or after execution.

    Listens by default to http://localhost:5000/
    """
    if paths is None or len(paths) == 0:
        paths_list = [os.getcwd()]
    else:
        paths_list = list(paths)
    inputs = []
    for prefix in paths_list:
        # if a dir is given BU does not point to a valid build dir,
        # attempt to resolve it.
        # Note that files are always kept, it ensure to the user to
        # provide a valid archive-formatted file
        for build in [prefix, os.path.join(prefix, NAME_BUILDIR)]:
            if utils.check_is_build_or_archive(build):
                io.console.debug(f"Adding build path / tarball from: {build}")
                inputs.append(os.path.abspath(build))
                break
        else:
            raise click.BadArgumentUsage(f"{prefix} is not a build directory nor an archive.")

    if ctx.obj["tui"]:
        if not TEXTUAL_AVAIL:
            raise click.BadOptionUsage("--tui", "Textual is not available.")

        from pcvs.ui.textual import report as gui

        return gui.start_app(inputs)

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
    return start_server(r)
