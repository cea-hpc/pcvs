import click
import yaml

from pcvsrt import config as pvConfig
from pcvsrt import profile as pvProfile
from pcvsrt import globals as pvGlobals
from pcvsrt import logs
from pcvsrt.cli.config import commands as cmdConfig


def compl_list_token(ctx, args, incomplete):  # pragma: no cover
    pvProfile.init()
    flat_array = []
    for scope in pvGlobals.storage_order():
        for elt in pvProfile.PROFILE_EXISTING[scope]:
            flat_array.append(scope + "." + elt[0])

    return [elt for elt in flat_array if incomplete in elt]


@click.group(name="profile", short_help="Manage Profiles")
@click.pass_context
def profile(ctx):
    """
    Profile management command. A profile is a gathering of multiple
    configuration blocks, describing a fixed validation process (for instance,
    the fixed compiler & runtime, on a given partition...). Profiles are stored
    on the file system and SCOPE allows to select which granularity the command
    applies:

    \b
    - LOCAL: refers to the current working directory
    - USER: refers to the current user HOME directory ($HOME)
    - GLOBAL: refers to PCVS-rt installation prefix
    """


@profile.command(name="list", short_help="List available profiles")
@click.argument("token", nargs=1, required=False,
                type=click.STRING, autocompletion=compl_list_token)
@click.pass_context
def profile_list(ctx, token):
    """
    List all known profiles to be used as part of a validation process. The
    list can be filtered out depending on the '--scope' option to only print
    out profiles available at a given granularity.
    """
    (scope, label) = (None, None)
    if token:
        (scope, label) = pvProfile.extract_profile_from_token(token,
                                                              single="left")

    if label:
        logs.warn("no LABEL required for this command")

    pvProfile.check_valid_scope(scope)

    logs.print_header("Profile View")
    profiles = pvProfile.list_profiles(scope)
    if not profiles:
        logs.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in pvGlobals.storage_order():
            # aggregate names for each sccope
            names = sorted([elt[0]
                            for elt in [array for array in profiles[sc]]])
            if not names:
                logs.print_item("{: <6s}: {}".format(sc.upper(),
                                                     logs.cl('None',
                                                             'bright_black')))
            else:
                logs.print_item("{: <6s}: {}".format(sc.upper(),
                                                     ", ".join(names)))
    else:
        names = sorted([x[0] for x in profiles])
        logs.print_item("{: <6s}: {}".format(scope.upper(), ", ".join(names)))

    # in case verbosity is enabled, add scope paths
    logs.info("Scopes are ordered as follows:")
    for i, scope in enumerate(pvGlobals.storage_order()):
        logs.info("{}. {}: {}".format(
            i+1, scope.upper(), pvGlobals.STORAGES[scope]))


@profile.command(name="show",
                 short_help="Prints single profile details")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.pass_context
def profile_show(ctx, token):
    """Prints a detailed view of the NAME profile."""
    (scope, label) = pvProfile.extract_profile_from_token(token)
    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        pf.load_from_disk()
        pf.display()
    else:
        logs.err("Profile '{}' not found!".format(token))
    pass


def profile_interactive_select():
    composition = {}
    logs.enrich_print("Hello! I'm Tux and I'm here to assist you building a "
                      "valid profile from a combination of configuration blocks."
                      " Lists are based on currently found files on "
                      "your system. If possible, a default block  will be"
                      " loaded".format(len(pvConfig.CONFIG_BLOCKS)), skippable=True)
    for kind in pvConfig.CONFIG_BLOCKS:
        logs.print_section("Pick up a {}".format(kind.capitalize()))
        choices = []
        for scope, avails in pvConfig.list_blocks(kind).items():
            for elt in avails:
                choices.append(".".join([scope, elt[0]]))

        idx = len(choices) + 1
        try:
            default = choices.index("global.default") + 1
        except ValueError:
            default = None
        for i, cell in enumerate(choices):
            logs.print_item("{}: {}".format(i + 1, cell))
        while idx < 0 or len(choices) <= idx:
            idx = click.prompt("Your selection", default, type=int) - 1
        (scope, _, label) = pvConfig.extract_config_from_token(
            choices[idx], pair="span")
        composition[kind] = pvConfig.ConfigurationBlock(kind, label, scope)

    return composition


@profile.command(name="build",
                 short_help="Build/copy a profile from basic conf blocks")
@click.option("-i", "--interactive", "interactive", show_envvar=True,
              default=False, is_flag=True,
              help="Build the profile by interactively selecting conf. blocks")
@click.option("-b", "--block", "blocks", multiple=True,
              default=False, show_envvar=True,
              autocompletion=cmdConfig.compl_list_token,
              help="non-interactive option to build a profile")
@click.option("-f", "--from", "clone", show_envvar=True,
              default=None, type=click.STRING,
              autocompletion=compl_list_token,
              help="Another profile to herit from.")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.pass_context
def profile_build(ctx, token, interactive, blocks, clone):
    """
    Creates a new profile based on basic configuration blocks (see the 'config'
    command). The newly created profile is built from basic configuration
    blocks. If some are not specified, their respective 'default' is loaded in
    replacement (following the scope priority order).

    The profile may also be copied from an existing one. The clone
    label is the exact profile name, prefixed (or not) with the scope this
    profile is stored (global.default, local.default....). Without further
    information, the scope priority is applied : local scope overrides a user
    scope, itself overriding a global scope.

    If command-line configuration-blocks and the `--from` option are used
    together, each configuration block will override its part of the newly
    created profile, respectively, allowing a clone-and-edit approach in a
    single command.

    The NAME argument attaches a label to the profile. The NAME has to start
    and end with an alphanumeric but no more restrictions are applied
    (e.g. 'mpi-srun-stampede-large' is allowed)
    """
    (p_scope, p_label) = pvProfile.extract_profile_from_token(token)

    pf = pvProfile.Profile(p_label, p_scope)
    if pf.is_found():
        logs.err("A profile named '{}' already exist!".format(
            pf.full_name), abort=1)

    pf_blocks = {}

    if clone is not None:
        (c_scope, c_label) = pvProfile.extract_profile_from_token(clone)
        base = pvProfile.Profile(c_label, c_scope)
        pf.clone(base)
        pass
    elif interactive:
        logs.print_header("profile view (build)")
        pf_blocks = profile_interactive_select()
        pf.fill(pf_blocks)
    else:
        for block in blocks:
            (b_sc, b_kind, b_label) = pvConfig.extract_config_from_token(block)
            cur = pvConfig.ConfigurationBlock(b_kind, b_label, b_sc)
            if cur.is_found() and b_kind not in pf_blocks.keys():
                pf_blocks[b_kind] = cur
            else:
                logs.err("Issue with '{}'".format(block))
                if not cur.is_found():
                    logs.err("Such configuration does not exist!")
                else:
                    logs.err(
                        "'{}' kind is set twice".format(b_kind.upper()),
                        "First is '{}'".format(pf_blocks[b_kind].full_name))
                logs.err("", abort=1)
        pf.fill(pf_blocks)

    logs.print_header("profile view")
    pf.flush_to_disk()
    # pf.display()

    logs.print_section("final profile (registered as {})".format(p_scope))
    for k, v in pf_blocks.items():
        logs.print_item("{: >9s}: {}".format(
            k.upper(), ".".join([v.scope, v.short_name])))


@profile.command(name="destroy",
                 short_help="Delete a profile from disk")
@click.confirmation_option(
    "-f", "--force", "force", expose_value=False,
    prompt="Are you sure you want to delete this profile ?",
    help="Do not ask for confirmation")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.pass_context
def profile_destroy(ctx, token):
    (scope, label) = pvProfile.extract_profile_from_token(token)

    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        if pf.scope == 'global' and label == 'local':
            logs.err("err", abort=1)
        else:
            pf.delete()
    else:
        logs.err("Profile '{}' not found!".format(label),
                 "Please check the 'list' command", abort=1)


@profile.command(name="alter",
                 short_help="Edit an existing profile")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.option("-e", "--editor", "editor", envvar="EDITOR", show_envvar=True,
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
def profile_alter(ctx, token, editor):
    (scope, label) = pvProfile.extract_profile_from_token(token)

    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        if pf.scope == 'global' and label == 'local':
            logs.err("err", abort=1)
        else:
            pf.open_editor(editor)
    else:
        logs.err("Profile '{}' not found!".format(label),
                 "Please check the 'list' command", abort=1)


@profile.command(name="import",
                 short_help="Import a file as a profile")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.argument("src_file", type=click.File('r'))
@click.option("--test", type=click.File('r'))
@click.pass_context
def profile_import(ctx, token, src_file):
    (scope, label) = pvProfile.extract_profile_from_token(token)
    pf = pvProfile.Profile(label, scope)
    if not pf.is_found():
        pf.fill(yaml.load(src_file.read(), Loader=yaml.Loader))
        pf.flush_to_disk()
    else:
        logs.err("Cannot import into an already created profile!", abort=1)


@profile.command(name="export",
                 short_help="Export a profile to a file")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.argument("dest_file", type=click.File('w'))
@click.pass_context
def profile_export(ctx, token, dest_file):
    (scope, label) = pvProfile.extract_profile_from_token(token)

    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        dest_file.write(yaml.dump(pf.dump()))
