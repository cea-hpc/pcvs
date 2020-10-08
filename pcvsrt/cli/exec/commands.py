import os
import click
import subprocess
from pcvsrt.helpers import log, io
from pcvsrt.cli.exec import backend as pvExec

@click.command(name="exec", short_help="Running aspecific test")
@click.option('-o', '--output', 'output', default=None,
              help="Directory where build artifacts are stored")
@click.option('-l', '--list', 'gen_list', is_flag=True,
              help='List available tests (may take a while)')
@click.argument("argument", type=str, required=False)
@click.pass_context
def exec(ctx, output, argument, gen_list):
    err = subprocess.STDOUT
    if gen_list:
        script_path = pvExec.retrieve_all_test_scripts(output)
        argument = "--list"
        err = subprocess.DEVNULL
    else:
        script_path = [pvExec.retrieve_test_script(argument, output)]
    try:
        for f in script_path:
            fds = subprocess.Popen(['sh', f, argument], stderr=err)
            fds.communicate()
    except subprocess.CalledProcessError as e:
        log.err("Error while running the test:", "{}".format(e.output.decode('ascii')))
