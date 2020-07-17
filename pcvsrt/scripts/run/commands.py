import click
import os
import pcvsrt.utils.logs as logs
from pcvsrt import main


@click.command(name="run", short_help="Run a validation")
@click.option("-p", "--profile", "profilename",
              default=None, type=str,
              help="an existing profile")
@click.option("-o", "--output", "output",
              default="./build", type=click.Path(exists=False),
              help="Where artefacts will be stored during/after the run")
@click.option("-l", "--tee", "log",
              default=True, is_flag=True,
              help="Log the whole stdout/stderr")
@click.option("-d", "--detach", "detach",
              default=True, is_flag=True,
              help="Run the validation asynchronously")
@click.option("--status", "status",
              default=None, is_flag=True,
              help="Display current run progression")
@click.option("--pause", "pause",
              default=None, is_flag=True,
              help="Pause the current run")
@click.option("--resume", "resume",
              default=None, is_flag=True,
              help="Resume a previously paused run")
@click.option("--bootstrap", "bootstrap",
              default=False, is_flag=True,
              help="Initialize basic test templates in given dirs")
@click.argument("list_of_dirs", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def run(ctx, profilename, output, log, detach, status,
        resume, pause, bootstrap, list_of_dirs):

    if bootstrap:
        logs.info("Bootstrapping directories")
        for directory in list_of_dirs:
            run.init_structure(directory)
        exit(0)

    if pause and resume:
        logs.err("Cannot pause and resume the run at the same time!")
    elif pause:
        logs.info("Pause the current run")
        exit(0)
    elif resume:
        logs.info("Resume the current run")
        exit(0)
    elif status:
        logs.info("Get status about the running validation")
        exit(0)

    logs.banner()

    settings = {}
    settings['verbose'] = ctx.obj['verbose']
    settings['color'] = ctx.obj['color']
    settings['pfname'] = profilename
    settings['output'] = output
    settings['tee'] = log
    settings['bg'] = detach

    logs.print_header("pre-actions")
    main.prepare(settings)
    main.load_benchmarks(list_of_dirs)

    logs.print_header("validation start")
    main.run()

    logs.print_header("post-treatment")
    main.terminate()
