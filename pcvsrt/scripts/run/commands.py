import click

@click.command(name="run", short_help="Run a validation")
@click.option("-v", "--verbose", "verbosity",
              multiple=True, is_flag=True, default=0,
              help="Verbosity (cumulative)")
@click.option("-s", "--select", "subdirs",
              multiple=True, default=".",
              help="directories to be parsed for current run")
@click.option("-p", "--profile", "profile",
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
def run(verbosity, subdirs, compiler_tag, runtime_tag, env_tag,
        output, log, resume, pause, status, list_of_dirs):
    print("Running the validation over %s" % list(list_of_dirs))
