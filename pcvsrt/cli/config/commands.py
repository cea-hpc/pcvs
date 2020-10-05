import click
import yaml

from pcvsrt.cli.config import backend as pvConfig
from pcvsrt.helpers import log, io


def compl_list_token(ctx, args, incomplete) -> list:  # pragma: no cover
    pvConfig.init()
    flat_array = []
    for kind in pvConfig.CONFIG_BLOCKS:
        for scope in io.storage_order():
            for elt in pvConfig.CONFIG_EXISTING[kind][scope]:
                flat_array.append(scope + "." + kind + "." + str(elt[0]))

    return [elt for elt in flat_array if incomplete in elt]


@click.group(name="config", short_help="Manage Configuration blocks")
@click.pass_context
def config(ctx) -> None:
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

    The scope option allows to select at which granularity the command applies:
    \b
    - LOCAL: refers to the current working directory
    - USER: refers to the current user HOME directory ($HOME)
    - GLOBAL: refers to PCVS-rt installation prefix
    """


def config_list_single_kind(kind, scope) -> None:
    """Related to 'config list' command, handling a single 'kind' at a time"""
    # retrieve blocks to print
    blocks = pvConfig.list_blocks(kind, scope)
    if not blocks:
        log.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in io.storage_order():
            # aggregate names for each sccope
            names = sorted([elt[0] for elt in [array for array in blocks[sc]]])
            if not names:
                log.print_item("{: <6s}: {}".format(
                                sc.upper(),
                                log.cl('None', 'bright_black')))
            else:
                log.print_item("{: <6s}: {}".format(
                                sc.upper(),
                                ", ".join(names)))
    else:
        names = sorted([x[0] for x in blocks])
        log.print_item("{: <6s}: {}".format(scope.upper(), ", ".join(names)))


@config.command(name="list", short_help="List available configuration blocks")
@click.argument("token", nargs=1, required=False,
                type=click.STRING, autocompletion=compl_list_token)
@click.pass_context
def config_list(ctx, token) -> None:
    """List available configurations on the system. The list can be
    filtered by applying a KIND. Possible values for KIND are documented
    through the `pcvs config --help` command.

    Additionally, a special KIND value has been added for this command
    command only: the 'all' keyword, listing all possible configuration files
    currently registered.
        'all' is a specific value to list all configurations.
    """
    (scope, kind, label) = (None, None, None)
    if token:
        (scope, kind, label) = pvConfig.extract_config_from_token(
            token, pair="left", single="center")
    if label:
        log.warn("no LABEL required for this command")

    # special cases for 'list' command:
    # - no 'label' are required (ignored otherwise)
    # - a special 'all' value is allowed for 'kind' parameter
    if kind is None or kind.lower() == 'all':
        kinds = pvConfig.CONFIG_BLOCKS
    else:
        pvConfig.check_valid_kind(kind)
        kinds = [kind]
    io.check_valid_scope(scope)

    log.print_header("Configuration view")

    for k in kinds:
        log.print_section("Kind '{}'".format(k.upper()))
        config_list_single_kind(k, scope)

    # in case verbosity is enabled, add scope paths
    log.info("Scopes are ordered as follows:")
    for i, scope in enumerate(io.storage_order()):
        log.info("{}. {}: {}".format(
            i+1, scope.upper(), io.STORAGES[scope]))


@config.command(name="show",
                short_help="Show detailed view of the selected configuration")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.pass_context
def config_show(ctx, token) -> None:
    """Prints a detailed description of this configuration block, labeled NAME
    and belonging to the KIND kind.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)

    block = pvConfig.ConfigurationBlock(kind, label, scope)
    if block.is_found():
        block.load_from_disk()
        block.display()
    else:
        sc = scope
        sc = "any" if sc is None else sc
        log.err("No '{}' configuration found at {} level!".format(
            label, sc))


@config.command(name="create", short_help="Create/Clone a configuration block")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.option("-f", "--from", "clone",
              default=None, type=str, show_envvar=True,
              help="Valid name to copy (may use scope, e.g. global.label)")
@click.pass_context
def config_create(ctx, token, clone) -> None:
    """Create a new configuration block for the given KIND. The newly created
    block will be labeled NAME. It is inherited from a default template. This
    can be overriden by spefifying a CLONE argument.

    The CLONE may be given raw (as a regular label) or prefixed by the scope
    this label is coming from. For instance, the user may pass 'global.mylabel'
    to disambiguate the selection if multiple configuration blocks with same
    names exist at different scopes.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)
    if clone is not None:
        (c_scope, c_kind, c_label) = pvConfig.extract_config_from_token(
            clone, pair='span')
        if c_kind is not None and c_kind != kind:
            log.err("Can only clone from a conf. blocks with the same KIND!",
                    abort=1)
        base = pvConfig.ConfigurationBlock(kind, c_label, c_scope)
        base.load_from_disk()
    else:
        base = pvConfig.ConfigurationBlock(kind, 'default', None)
        base.load_template()

    copy = pvConfig.ConfigurationBlock(kind, label, scope)
    if not copy.is_found():
        copy.clone(base)
        copy.flush_to_disk()
    else:
        log.err("Configuration '{}' already exists!".format(
            copy.full_name))


@config.command(name="destroy", short_help="Remove a config block")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.confirmation_option(
    "-f", "--force",
    prompt="Are you sure you want to delete this config ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def config_destroy(ctx, token) -> None:
    """
    Erase from disk a previously created configuration block.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)

    c = pvConfig.ConfigurationBlock(kind, label, scope)
    if c.is_found():
        c.delete()
    else:
        log.err("Configuration '{}' not found!".format(label),
                "Please check the 'list' command")


@config.command(name="edit", short_help="edit the config block")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.option("-e", "--editor", "editor", envvar="EDITOR", show_envvar=True,
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
def config_edit(ctx, token, editor) -> None:
    """
    Open the file with $EDITOR for direct modifications. The configuration is
    then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)

    block = pvConfig.ConfigurationBlock(kind, label, scope)
    if block.is_found():
        block.open_editor(editor)
        block.flush_to_disk()
    else:
        log.err("Cannot open this configuration: does not exist!")


@config.command(name="import", short_help="Import config from a file")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.argument("in_file", type=click.File('r'))
@click.pass_context
def config_import(ctx, token, in_file) -> None:
    """
    Import a new configuration block from a YAML file named IN_FILE.
    The configuration is then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)

    obj = pvConfig.ConfigurationBlock(kind, label, scope)
    if not obj.is_found():
        obj.fill(yaml.load(in_file.read(), Loader=yaml.Loader))
        obj.flush_to_disk()
    else:
        log.err("Cannot import into an already created conf. block!")


@config.command(name="export", short_help="Export config into a file")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.argument("out_file", type=click.File('w'))
@click.pass_context
def config_export(ctx, token, out_file):
    """
    Export a new configuration block to a YAML file named OUT_FILE.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    (scope, kind, label) = pvConfig.extract_config_from_token(token)

    obj = pvConfig.ConfigurationBlock(kind, label, scope)
    if obj.is_found():
        out_file.write(yaml.dump(obj.dump()))
    else:
        log.err("Failed to export '{}': not found!".format(token))
