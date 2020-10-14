from pcvsrt.helpers.system import Settings
import click
import copy
import base64
from prettytable import PrettyTable
import subprocess
from pcvsrt.helpers import log, io, system
from pcvsrt.cli.utilities import backend as pvUtils


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
        script_path = pvUtils.retrieve_all_test_scripts(output)
        argument = "--list"
        err = subprocess.DEVNULL
    else:
        script_path = [pvUtils.retrieve_test_script(argument, output)]
    try:
        for f in script_path:
            fds = subprocess.Popen(['sh', f, argument], stderr=err)
            fds.communicate()
    except subprocess.CalledProcessError as e:
        log.err("Error while running the test:", "{}".format(e.output.decode('ascii')))


@click.command(name="check", short_help="Ensure future input will be conformant to standards")
@click.option("--encoding", "-E", "encoding", default=False, is_flag=True,
              help="Check capability to print utf-8 characters properly")
@click.option("--colouring", "-x", "color", default=False, is_flag=True,
              help="Check capability to print coloured characters properly")
@click.option("--directory", "-d", "dir", default=None,
             type=click.Path(exists=True, file_okay=False),
             help="Check correctness for pcvs.* files")
@click.option("--configs", "-c", "configs", default=False, is_flag=True,
              help="Check correctness for all registered configuation block")
@click.option("--profiles", "-p", "profiles", default=False, is_flag=True,
              help="Check correctness for all registered profiles")

@click.pass_context
def check(ctx, dir, encoding, color, configs, profiles):
    log.banner()
    errors = dict()
    if color:
        log.print_header("Colouring")
        t = PrettyTable()
        ctx.color = True
        t.field_names = ["Name", "Foreground", "Background"]
        for k in sorted(log.all_colors):
            t.add_row([k, click.style("Test", fg=k), click.style("Test", bg=k)])
        print(t)

    if encoding:
        log.print_header("Encoding")
        
        t = PrettyTable()
        t.field_names = ["Alias", "Symbol", "Fallback"]
        log.__set_encoding(False)
        fallback = copy.deepcopy(log.glyphs)
        log.__set_encoding(True)

        for k in sorted(log.glyphs.keys()):
            t.add_row([k, log.glyphs[k], fallback[k]])
        print(t)
    
    if configs:
        log.print_header("Configurations")
        errors = {**errors, **pvUtils.process_check_configs()}

    if profiles:
        log.print_header("Profile(s)")
        errors = {**errors, **pvUtils.process_check_profiles()}

    if dir:
        log.print_header("Test directories")
        log.print_section("Prepare the environment")
        # first, replace build dir with a temp one
        settings = Settings()
        cfg_val = system.CfgValidation()
        cfg_val.override('output', "/tmp/test")
        settings.validation = cfg_val

        system.save_as_global(settings)

        system.get('validation').output = "/tmp/test"
        errors = {**errors, **pvUtils.process_check_directory(dir)}

    if errors:
        log.print_section("Classification of errors:")
        table = PrettyTable()
        table.field_names = ["Count", "Type of error"]
        
        for k, v in errors.items():
            table.add_row([v, base64.b64decode(k).decode('ascii')])

        table.align["Count"] = "c"
        table.align["Type of error"] = ""
        table.sortby = "Count"
        table.reversesort = True
        print(table)
    else:
        log.print_section("{succ} {cg} {succ}".format(
            succ=log.utf('succ'),
            cg=log.cl("Everything is OK!", 'green', bold=True))
        )
