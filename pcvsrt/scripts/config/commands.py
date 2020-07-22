import click
import yaml
import pcvsrt
from pcvsrt.utils import logs


@click.group(name="config", short_help="Manage Configuration blocks")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="Scope level the current configuration applies")
@click.pass_context
def config(ctx, scope):
    """The 'config' command helps user to manage configuration basic blocks in
    order to set up a future validation to process. A basic block is the
    smallest piece of configuration gathering similar informations. Multiple
    KIND exist:

    \b
    - COMPILER : relative to compiler configuration (CC, CXX, FC...)
    - RUNTIME  : relative to test execution (MPICC...)
    - MACHINE  : describes a machine to potentially run validations (nodes...)
    - CRITERION: defines piec of information to validate on (a.k.a. iterators')
    - GROUP    : templates used as a convenience to filter out tests globally
    """
    ctx.obj['scope'] = scope.lower() if scope is not None else None


def config_list_single_kind(kind, scope):
    """Related to 'config list' command, handling a single 'kind' at a time"""
    # retrieve blocks to print
    blocks = pcvsrt.config.list_blocks(kind, scope)
    if not blocks:
        logs.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in pcvsrt.config.scope_order():
            # aggregate names for each sccope
            names = [elt[0] for elt in [array for array in blocks[sc]]]
            if not names:
                logs.print_item("{: <6s}: {}None".format(sc.upper(),
                                                         logs.cl('grey')))
            else:
                logs.print_item("{: <6s}: {}".format(sc.upper(),
                                                     ", ".join(names)))
    else:
        names = [x[0] for x in blocks]
        logs.print_item("{: <6s}: {}".format(scope.upper(), ", ".join(names)))


@config.command(name="list", short_help="List available configuration blocks")
@click.argument("kind", nargs=1, type=str, required=False)
@click.pass_context
def config_list(ctx, kind):
    """List available configurations on the system. The list can be
    filtered by applying a KIND. Possible values for KIND are documented
    through the `pcvs config --help` command.

    Additionally, a special KIND value has been added for this command
    command only: the 'all' keyword, listing all possible configuration files
    currently registered.
        'all' is a specific value to list all configurations.
    """
    
    if kind is None or kind.lower() == 'all':
        kinds = pcvsrt.config.CONFIG_BLOCKS
    else:
        pcvsrt.config.check_valid_kind(kind)
        kinds = [kind]

    logs.print_header("Configuration view")

    for k in kinds:
        logs.print_section("Kind '{}'".format(k.upper()))
        config_list_single_kind(k, ctx.obj['scope'])

    # in case verbosity is enabled, add scope paths
    logs.info("Scopes are labeled as follows:")
    for scope, prefix in pcvsrt.config.CONFIG_STORAGES.items():
        logs.info("- {}: {}".format(scope.upper(), prefix))


@config.command(name="show",
                short_help="Show detailed view of the selected configuration")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.pass_context
def config_show(ctx, kind, name):
    """Prints a detailed description of this configuration block, labeled NAME
    and belonging to the KIND kind.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    block = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if block.is_found():
        block.load_from_disk()
        block.display()
    else:
        sc = ctx.obj['scope']
        sc = "any" if sc is None else sc
        logs.err("No '{} configuration found at {} level!".format(name, sc) )


@config.command(name="create", short_help="Create/Clone a configuration block")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-f", "--from", "clone",
              default=None, type=str,
              help="Valid name to copy (may use scope, e.g. global.label)")
@click.pass_context
def config_create(ctx, kind, name, clone):
    """Create a new configuration block for the given KIND. The newly created
    block will be labeled NAME. It herits from a default template. This can be
    overriden by spefifying a CLONE argument.

    The CLONE may be given raw (as a regular label) or prefixed by the scope
    this label is coming from. For instance, the user may pass 'global.mylabel'
    to disambiguate the selection if multiple configuration blocks with same
    names exist at different scopes.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    if clone is not None:
        array = clone.split(".")
        clone_scope = array[0] if len(array) > 1 else None
        base = pcvsrt.config.ConfigurationBlock(kind, array[-1], clone_scope)
        base.load_from_disk()
    else:
        base = pcvsrt.config.ConfigurationBlock(kind, 'default', None)
        base.load_template()

    copy = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if not copy.is_found():
        copy.clone(base, ctx.obj['scope'])
        copy.flush_to_disk()
    else:
        logs.err("Configuration '{}' already exists! ({})".format(name, copy.scope))


@config.command(name="destroy", short_help="Remove a config block")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-f", "--force", "force",
              is_flag=True, default=False,
              help="Do not ask for confirmation before deletion")
@click.pass_context
def config_destroy(ctx, force, name, kind):
    """
    Erase from disk a previously created configuration block.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    c = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if c.is_found():
        if not force:
            if not click.confirm("Are you sure to delete '{}' ({})?".format(name, c.scope)):
                return
        c.delete()
    else:
        logs.err("Configuration '{}' not found!".format(name), "Please check the 'list' command", abort=1)


@config.command(name="edit", short_help="edit the config block")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.option("-e", "--editor", "editor",
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
def config_edit(ctx, kind, name, editor):
    """
    Open the file with $EDITOR for direct modifications. The configuration is
    then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    block = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if block.is_found():
        block.open_editor(editor)
        block.flush_to_disk()


@config.command(name="import", short_help="Import config from a file")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.argument("in_file", type=click.File('r'))
@click.pass_context
def config_import(ctx, kind, name, in_file):
    """
    Import a new configuration block from a YAML file named IN_FILE.
    The configuration is then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    obj = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if obj.is_found():
        obj.fill(yaml.load(in_file.read(), Loader=yaml.Loader))
        obj.flush_to_disk()


@config.command(name="export", short_help="Export config into a file")
@click.argument("kind", nargs=1, type=str)
@click.argument("name", nargs=1, type=str)
@click.argument("out_file", type=click.File('w'))
@click.pass_context
def config_export(ctx, kind, name, out_file):
    """
    Export a new configuration block to a YAML file named OUT_FILE.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    obj = pcvsrt.config.ConfigurationBlock(kind, name, ctx.obj['scope'])
    if obj.is_found():
        out_file.write(yaml.dump(obj.dump()))
    