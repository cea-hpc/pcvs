import sys
from pathlib import Path
from typing import TextIO

from pcvs import io
from pcvs.backend import configfile
from pcvs.backend.configfile import ConfigFile
from pcvs.helpers.storage import ConfigDesc
from pcvs.helpers.storage import ConfigKind
from pcvs.helpers.storage import ConfigLocator
from pcvs.helpers.storage import ConfigScope

try:
    import rich_click as click

    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click  # type: ignore

from click.utils import LazyFile


def compl_list_scope_kind(
    ctx: click.Context, param: click.Parameter, incomplete: str  # pylint: disable=unused-argument
) -> list[str]:
    """Config Scope + Kind completion function."""
    all_name = [f"{str(elt.scope)}:{str(elt.kind)}" for elt in ConfigLocator().list_all_configs()]
    all_scope_kind_pair = sorted(set(all_name))
    return [elt for elt in all_scope_kind_pair if incomplete in elt]


def compl_list_configs(
    ctx: click.Context, param: click.Parameter, incomplete: str  # pylint: disable=unused-argument
) -> list[str]:
    """All configs name completion function."""
    return [
        elt.full_name for elt in ConfigLocator().list_all_configs() if incomplete in elt.full_name
    ]


def compl_list_user_configs(
    ctx: click.Context, param: click.Parameter, incomplete: str  # pylint: disable=unused-argument
) -> list[str]:
    """User only configs name completion function."""
    return [
        elt.full_name
        for elt in ConfigLocator().list_all_configs()
        if incomplete in elt.full_name and elt.scope != ConfigScope.GLOBAL
    ]


@click.group(
    name="config",
    short_help="Manage Configurations",
)
def cli_config() -> None:  # pylint: disable=unused-argument
    """
    The 'config' command helps user to manage configurations.
    Their is multiples KIND of configurations:

    \b
    - COMPILER  : relative to compiler configuration (CC, CXX, FC...)
    - RUNTIME   : relative to test execution (MPICC...)
    - MACHINE   : describes a machine to potentially run validations (nodes...)
    - CRITERION : defines pieces of information to validate on (a.k.a. iterators')
    - GROUP     : templates used as a convenience to filter out tests globally
    \b
    - PROFILE   : references for 1 of each of the 5 configurations above, used by `pcvs run`.
    \b
    - PLUGIN    : an additional python plugin to filter criterions, specify in the runtime config.
    \b
    The scope option allows to select at which granularity the command applies:
    \b
    - LOCAL     : refers to the current working directory
    - USER      : refers to the current user HOME directory ($HOME)
    - GLOBAL    : refers to PCVS-rt installation prefix
    \b
    Run `pcvs config list` to get a list of all configs and the path associated with each scopes.
    \b
    The `pcvs config ...` subcommands request a 'token' to reference a configuration.
    Those tokens are a combination of a config SCOPE, a config KIND and the config name
    formatted as follow 'scope:kind:name'.
    (Look at section 'Getting Started' in the documentation to get auto completion !!)
    """


@cli_config.command(
    name="list",
    short_help="List available configuration blocks",
)
@click.argument(
    "token",
    nargs=1,
    required=False,
    type=str,
    shell_complete=compl_list_scope_kind,
    # help="Token in the form scope[:kind] or kind",
)
@click.pass_context
def cli_config_list(
    ctx: click.Context, token: str | None  # pylint: disable=unused-argument
) -> None:
    """
    List available configurations on the system.

    The list can be filtered by applying a KIND.
    Possible values for KIND are documented through the `pcvs config --help` command.
    """
    if token is None:
        scope, kinds = None, ConfigKind.all_kinds()
    else:
        scope, kind = ConfigLocator().parse_scope_and_kind_raise(token)
        kinds = [kind] if kind is not None else ConfigKind.all_kinds()

    io.console.print_header("Configuration view")
    for k in kinds:
        io.console.print_section(f"Kind '{str(k).upper()}'")
        scopes = [scope] if scope else ConfigScope.all_scopes()
        for sc in scopes:
            configs = ConfigLocator().list_configs(k, sc)
            names = sorted([c.name for c in configs])
            if len(names) == 0:
                io.console.print_item(f"[bright_black]{str(sc): <6s}: None")
            else:
                io.console.print_item(f"{str(sc): <6s}: {names}")

    io.console.print("Scopes are ordered as follows:")
    for i, sc in enumerate(ConfigScope.all_scopes()):
        io.console.print(f"{i + 1}. {str(sc).upper()}: {ConfigLocator().get_storage_dir(sc)}")


@cli_config.command(
    name="show",
    short_help="Show detailed view of the selected configuration",
)
@click.argument(
    "token",
    nargs=1,
    type=str,
    shell_complete=compl_list_configs,
    # help="Token in the form [scope:[kind:]]label",
)
@click.pass_context
def cli_config_show(ctx: click.Context, token: str) -> None:  # pylint: disable=unused-argument
    """
    Prints a detailed description of this configuration block, labeled NAME
    and belonging to the KIND kind.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token, should_exist=True)
    configfile.get_conf(cd).display()


@cli_config.command(
    name="create",
    short_help="Create/Clone a configuration block",
)
@click.argument(
    "token",
    nargs=1,
    type=str,
)
@click.option(
    "-c",
    "--clone",
    "clone",
    default=None,
    type=str,
    show_envvar=True,
    shell_complete=compl_list_configs,
    help="Valid name to copy (may use scope, e.g. global.label)",
)
@click.option(
    "-i/-I",
    "--interactive/--no-interactive",
    "interactive",
    default=False,
    is_flag=True,
    help="Directly open the created config block in $EDITOR",
)
@click.pass_context
def cli_config_create(
    ctx: click.Context,  # pylint: disable=unused-argument
    token: str,
    clone: str | None,
    interactive: bool,
) -> None:
    """
    Create a new configuration block for the given KIND.

    The newly created block will be labeled NAME.
    It is inherited from a default template.
    This can be overridden by specifying a CLONE argument.

    The CLONE may be given raw (as a regular label) or prefixed by the scope
    this label is coming from. For instance, the user may pass 'global.mylabel'
    to disambiguate the selection if multiple configuration blocks with same
    names exist at different scopes.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token, should_exist=False)

    if cd.exist:
        raise click.BadArgumentUsage(f"Configuration '{cd.full_name}' already exists!")
    if cd.scope == ConfigScope.GLOBAL:
        raise click.BadArgumentUsage(
            f"Can't create configuration '{cd.full_name}' in installation scope !"
        )

    conf: ConfigFile = configfile.get_conf(cd)

    if clone is not None:
        cdc: ConfigDesc = ConfigLocator().parse_full_raise(clone, should_exist=True)
        if cdc.kind != cd.kind:
            raise click.BadArgumentUsage("Can only clone from a conf blocks with the same KIND!")
        conf.from_str(configfile.get_conf(cdc).to_str())
    else:
        # if base is not specify, copy from default config
        default_config = ConfigLocator().find_config(Path("default"), cd.kind, ConfigScope.GLOBAL)
        assert default_config is not None
        conf.from_str(configfile.get_conf(default_config).to_str())

    conf.flush_to_disk()

    if interactive:
        conf.edit()


@cli_config.command(
    name="destroy",
    short_help="Remove a config block",
)
@click.argument(
    "token",
    nargs=1,
    type=str,
    shell_complete=compl_list_user_configs,
)
@click.confirmation_option(
    "-f",
    "--force",
    prompt="Are you sure you want to delete this config ?",
    help="Do not ask for confirmation before deletion",
)
@click.pass_context
def cli_config_destroy(ctx: click.Context, token: str) -> None:  # pylint: disable=unused-argument
    """
    Erase from disk a previously created configuration block.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token, should_exist=True)
    if cd.scope == ConfigScope.GLOBAL:
        raise click.BadArgumentUsage(
            f"Can't destroy configuration '{cd.full_name}' in installation scope !"
        )
    configfile.get_conf(cd).delete()


@cli_config.command(
    name="edit",
    short_help="edit the config block",
)
@click.argument(
    "token",
    nargs=1,
    type=click.STRING,
    shell_complete=compl_list_user_configs,
)
@click.pass_context
def cli_config_edit(ctx: click.Context, token: str) -> None:  # pylint: disable=unused-argument
    """
    Open the file with $EDITOR for direct modifications. The configuration is
    then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token, should_exist=True)
    if cd.scope == ConfigScope.GLOBAL:
        raise click.BadArgumentUsage(
            f"Can't edit configuration '{cd.full_name}'.\n"
            "Edit of config in installation scope are disable!\n"
            "Use config 'create --clone conf name' to clone default configs."
        )
    configfile.get_conf(cd).edit()


@cli_config.command(
    name="import",
    short_help="Import config from a file",
)
@click.argument(
    "token",
    nargs=1,
    type=click.STRING,
    shell_complete=compl_list_user_configs,
)
@click.option(
    "-s",
    "--source",
    "in_file",
    type=click.File("r"),
    default=sys.stdin,
)
@click.option(
    "-f",
    "--force",
    "force",
    is_flag=True,
    default=False,
    help="Erase any previously existing config.",
)
@click.pass_context
def cli_config_import(
    ctx: click.Context,  # pylint: disable=unused-argument
    token: str,
    in_file: TextIO,
    force: bool,
) -> None:
    """
    Import a new configuration block from a YAML file named IN_FILE.
    The configuration is then validated to ensure consistency.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token)
    if cd.scope == ConfigScope.GLOBAL:
        raise click.BadArgumentUsage(
            f"Can't import configurations '{cd.full_name}' in installation scope !"
        )
    conf: ConfigFile = configfile.get_conf(cd)
    if conf.exist and not force:
        raise click.BadArgumentUsage(
            f"Configuration '{cd.full_name}' already exist! To override existing configuration use '-f'."
        )
    conf.do_import(in_file.read())


@cli_config.command(
    name="export",
    short_help="Export config into a file",
)
@click.argument(
    "token",
    nargs=1,
    type=click.STRING,
    shell_complete=compl_list_configs,
)
@click.option(
    "-o",
    "--output",
    "out_file",
    type=click.File("w"),
    default=sys.stdout,
)
@click.pass_context
def cli_config_export(
    ctx: click.Context, token: str, out_file: LazyFile  # pylint: disable=unused-argument
) -> None:
    """
    Export a new configuration block to a YAML file named OUT_FILE.

    Possible values for KIND are documented
    through the `pcvs config --help` command.
    """
    cd: ConfigDesc = ConfigLocator().parse_full_raise(token, should_exist=True)
    conf: ConfigFile = configfile.get_conf(cd)

    out_file.write(conf.to_str())
