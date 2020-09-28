import os
import click
from pcvsrt.helpers import log, io


@click.command(name="debug", short_help="Help users manage PCVS tests & architecture")
@click.option("-f", "--test-files", "test_files",
              multiple=True, type=click.Path(exists=True),
              help="Analyze given path to detect any badly formatted input file"
              )
@click.pass_context
def debug(ctx, test_files):
    log.warn("TBD")
    pass
