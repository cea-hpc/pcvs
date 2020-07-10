import click
from pcvsrt import utils


POSSIBLE_CONFIGS = ['compilers', 'runtimes', 'envs', 'machines', 'validations']

__DEFAULT_STR_SUBGROUP = "A configuration SUBGROUP token is one among:" + ",".join(POSSIBLE_CONFIGS)
@click.group(name="config", short_help="Manage Configuration basic blocks")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="Scope where this command applies")
@click.pass_context
def config(ctx, scope):
    pass

@config.command(name="list", short_help="List configuration blocks")
@click.argument("subgroup", nargs=1, type=str)
@click.pass_context
def config_list(ctx, subgroup):
    """Applied to SUBGROUP configuration subroup. __DEFAULT_STR_SUBGROUP"""
    pass


@config.command(name="show", short_help="Display configuration block details")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.pass_context
def config_show(ctx, subgroup, name):
    """Show configuration details for NAME (as a block from SUBGROUP"""
    pass


@config.command(name="create", short_help="Create/Clone a config block")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-f", "--from", "clone",
              default=None, type=str,
              help="Valid configuration to copy from")
@click.pass_context
def config_create(ctx, subgroup, name):
    pass


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
    utils.open_in_editor(name)
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
