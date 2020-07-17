import click
import os
import shutil
import pcvsrt.utils.logs as logs
import pcvsrt.config as config

PREFIXPATH = "../.."
BASEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), PREFIXPATH))

@click.group(name="config", short_help="Manage Configuration basic blocks")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="Scope where this command applies")
@click.pass_context
def config(ctx, scope):
    if scope is None:
        scope = "local"
    ctx.obj['scope'] = scope.lower()
    pass


@config.command(name="list", short_help="List configuration blocks")
@click.argument("subgroup", nargs=1, type=str, required=False)
@click.pass_context
def config_list(ctx, subgroup):
    """Applied to SUBGROUP configuration subgroup.
    
        'all' is a specific value to list all configurations.
    """

    if not subgroup or 'all' == subgroup:
        blocks = [config.ConfigurationBlock(confType) for confType in config.CONFIG_BLOCKS]
    else:
        blocks = [config.ConfigurationBlock(subgroup)]
    
    for block in blocks:
        logs.print_header("Available configurations for '{}':".format(block.get_type().upper()))
        for k, v in block.get_configs().items():
            logs.print_step("{}: {}".format(k.upper(), ", ".join(v)))

    logs.info("Scopes are labeled as follows:")
    for scope, prefix in config.CONFPATHS.items():
        logs.info("- {}: {}".format(scope, prefix))


def __check_existing_file(scope, subpath):
    f = os.path.join(CONFPATHS[scope], subpath)
    print("exist-file: {}".format(f))
    if os.path.exists(f):
        return f
    else:
        return None


@config.command(name="show", short_help="Display configuration block details")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.pass_context
def config_show(ctx, subgroup, name):
    """Show configuration details for NAME (as a block from SUBGROUP"""
    f = __compute_config_path(ctx.obj['scope'], subgroup, name + ".yml", should_exist=True)
    print("opening: {}".format(f))
    fh = open(f, 'r')
    print(fh.read())
    fh.close()

    pass


@config.command(name="create", short_help="Create/Clone a config block")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-f", "--from", "clone",
              default="default", type=str,
              help="Valid configuration to copy from")
@click.pass_context
def config_create(ctx, subgroup, name, clone):
    filepath = __compute_config_path(ctx.obj['scope'], subgroup, name + ".yml", should_exist=False)
    clonepath = __compute_config_path(None, subgroup, "default.yml", should_exist=True)
    assert (clonepath)
   
    shutil.copyfile(clonepath, filepath)


@config.command(name="destroy", short_help="Remove a config block")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-f", "--force", "force",
              is_flag=True, default=False,
              help="Do not ask for confirmation")
@click.pass_context
def config_destroy(ctx, force, name):
    if not force:
        if not click.confirm("Are you sure to delete '{}' ?".format(name)):
            return
    print("deleted")
    pass


@config.command(name="edit", short_help="edit the config block")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-e", "--editor", "editor",
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
def config_edit(ctx, subgroup, name, editor):
    pass


@config.command(name="import", short_help="Import config from a file")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.argument("in_file", type=click.File('r'))
@click.pass_context
def config_import(ctx, subgroup, name, in_file):
    pass


@config.command(name="export", short_help="Export config into a file")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.argument("out_file", type=click.File('w'))
@click.pass_context
def config_export(ctx, subgroup, name, out_file):
    pass
