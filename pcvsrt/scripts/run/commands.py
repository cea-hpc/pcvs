import click

@click.command(name="run", short_help="Run a test base")
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
              default="./build", type=click.Path(),
              help="Where artefacts will be stored during/after the run")
@click.option("-l", "--tee", "log",
              default=True, is_flag=True,
              help="Log the whole stdout/stderr")
@click.argument("list_of_dirs", nargs=-1, type=click.Path(exists=True))
def run(verbosity, subdirs, compiler_tag, runtime_tag, env_tag,
        output, log, list_of_dirs):
    print("Running the validation over %s" % list(list_of_dirs))