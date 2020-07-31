import os

import click

from pcvsrt import run as pvRun
from pcvsrt.cli.profile import commands as cmdProfile
from pcvsrt import files, logs


@click.command(name="run", short_help="Run a validation")
@click.option("-p", "--profile", "profilename", default="default",
              autocompletion=cmdProfile.compl_list_token,
              type=str, show_envvar=True, help="an existing profile")
@click.option("-o", "--output", "output", default="./build", show_envvar=True,
              type=click.Path(exists=False, file_okay=False),
              help="Where artefacts will be stored during/after the run")
@click.option("-c", "--set-defaults", "set_default",
              default=None, is_flag=True,
              help="Set default values for run options (WIP)")
@click.option("-l", "--tee", "log", show_envvar=True,
              default=False, is_flag=True,
              help="Log the whole stdout/stderr")
@click.option("-d", "--detach", "detach",
              default=True, is_flag=True, show_envvar=True,
              help="Run the validation asynchronously")
@click.option("--status", "status",
              default=False, is_flag=True, show_envvar=True,
              help="Display current run progression")
@click.option("-P", "--pause", "pause",
              default=None, is_flag=True, show_envvar=True,
              help="Pause the current run")
@click.option("-R", "--resume", "resume",
              default=None, is_flag=True, show_envvar=True,
              help="Resume a previously paused run")
@click.option("-b", "--bootstrap", "bootstrap",
              default=False, is_flag=True, show_envvar=True,
              help="Initialize basic test templates in given dirs")
@click.option("-f", "--override", "override",
              default=False, is_flag=True, show_envvar=True,
              help="Allow to reuse an already existing output dir")
@click.argument("list_of_dirs", nargs=-1, type=str)
@click.pass_context
def run(ctx, profilename, output, log, detach, status,
        resume, pause, bootstrap, override, set_default, list_of_dirs):
    """
    Execute a validation suite from a given PROFILE.

    By default the current directory is scanned to find test-suites to run.
    May also be provided as a list of directories as described by tests
    found in LIST_OF_DIRS.
    """
    # parse non-run situations
    if bootstrap:
        logs.info("Bootstrapping directories")
        for directory in list_of_dirs:
            run.init_structure(directory)
        exit(0)
    elif pause and resume:
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
    elif set_default:
        files.open_in_editor("defaults")
        exit(0)

    # fill validation settings
    settings = {}
    # for any 'None' value, a load from default should be made
    settings['verbose'] = ctx.obj['verbose']
    settings['color'] = ctx.obj['color']
    settings['pfname'] = profilename
    settings['output'] = os.path.join(os.path.abspath(output), ".pcvs")
    settings['tee'] = log
    settings['bg'] = detach
    settings['override'] = override

    # analys directory list
    dict_of_dirs = {}
    err_dirs = []
    if not list_of_dirs:  # if not specified
        curdir = os.getcwd()
        dict_of_dirs[os.path.basename(curdir)] = curdir
    else:  # once specified
        for d in list_of_dirs:
            if ':' in d:  # split under LABEL:PATH semantics
                [label, testpath] = d.split(':')
                testpath = os.path.abspath(testpath)
            else:  # otherwise, LABEL = dirname
                testpath = os.path.abspath(d)
                label = os.path.basename(testpath)

            # if path does not exist
            if not os.path.isdir(testpath):
                err_dirs.append(testpath)

            dict_of_dirs[label] = testpath

    # list all non-existent dirs
    if err_dirs:
        logs.err("Following arguments should be valid paths:")
        for p in err_dirs:
            logs.err('- {}'.format(p))
        logs.err("please see '--help' for more information", abort=1)

    logs.banner()

    logs.print_header("pre-actions")
    pvRun.prepare(settings)

    pvRun.load_benchmarks(dict_of_dirs)

    logs.print_header("validation start")
    pvRun.run()

    logs.print_header("post-treatment")
    pvRun.terminate()
