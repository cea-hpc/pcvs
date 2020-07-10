import click


POSSIBLE_CONFIGS = ['compilers', 'runtimes', 'envs', 'machines', 'validations']

__DEFAULT_STR_SUBGROUP = "A configuration SUBGROUP token is one among:" + ",".join(POSSIBLE_CONFIGS)
@click.group(name="config", short_help="Manage Configuration basic blocks")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="select scope")
@click.pass_context
def config(ctx, scope):
    pass

@config.command(name="list", short_help="list available configuration blocks")
@click.argument("subgroup", nargs=1, type=str)
@click.pass_context
def config_list(ctx, type):
    """Applied to SUBGROUP configuration subroup. __DEFAULT_STR_SUBGROUP"""
    pass


@config.command(name="show", short_help="Display a given config basic block")
@click.argument("subgroup", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.pass_context
def config_show(ctx):
    """Show configuration details for NAME (as a block from SUBGROUP"""
    pass


@config.command(name="create", short_help="Create a new config basic block")
@click.argument("subgroup", nargs=1, type=str)
@click.option("-f", "--from", "clone",
              default=None, type=str,
              help="create from a clone (=copy)")
@click.pass_context
def config_create(ctx):
    pass


@config.command(name="destroy")
@click.argument("subgroup", nargs=1, type=str)
@click.pass_context
def config_destroy(ctx):
    pass


@config.command(name="edit")
@click.pass_context
def config_edit(ctx):
    pass


@config.command(name="import")
@click.argument("in_file", type=click.File('r'))
@click.pass_context
def config_import(ctx, in_file):
    pass


@config.command(name="export")
@click.argument("out_file", type=click.File('w'))
@click.pass_context
def config_export(ctx, out_file):
    pass
