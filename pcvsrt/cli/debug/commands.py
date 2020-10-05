import os
import click
import subprocess
from pcvsrt.helpers import log, io
from pcvsrt.cli.debug import backend as pvDebug

@click.command(name="debug", short_help="Help users manage PCVS tests & architecture")
@click.option('-t', '--type', 'dtype',
              type=click.Choice(['testname', 'path']), default="testname",
              help="Type of debug to perform")
@click.argument("argument", type=str)
@click.pass_context
def debug(ctx, dtype, argument):
    if dtype == 'testname':
        script_path = pvDebug.retrieve_test_script(argument)
        try:
            subprocess.check_output(['sh', script_path, argument], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            log.err("Error while running the test:", "{}".format(e.output.decode('ascii')))

    else:
        log.warn("Work in progress :)")

    pass
