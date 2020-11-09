import click
import yaml

from pcvsrt.cli.config import backend as pvConfig
from pcvsrt.cli.config import commands as cmdConfig
from pcvsrt.cli.profile import backend as pvProfile
from pcvsrt.helpers import io, log


def compl_list_token(ctx, args, incomplete):  # pragma: no cover
    pvProfile.init()
    flat_array = []
    for scope in io.storage_order():
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
        log.warn("no LABEL required for this command")

    io.check_valid_scope(scope)

    log.print_header("Profile View")
    profiles = pvProfile.list_profiles(scope)
    if not profiles:
        log.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in io.storage_order():
            # aggregate names for each sccope
            names = sorted([elt[0]
                            for elt in [array for array in profiles[sc]]])
            if not names:
                log.print_item("{: <6s}: {}".format(sc.upper(),
                                                    log.cl('None',
                                                             'bright_black')))
            else:
                log.print_item("{: <6s}: {}".format(sc.upper(),
                                                    ", ".join(names)))
    else:
        names = sorted([x[0] for x in profiles])
        log.print_item("{: <6s}: {}".format(scope.upper(), ", ".join(names)))

    # in case verbosity is enabled, add scope paths
    log.info("Scopes are ordered as follows:")
    for i, scope in enumerate(io.storage_order()):
        log.info("{}. {}: {}".format(
            i+1, scope.upper(), io.STORAGES[scope]))


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
        raise click.BadArgumentUsage("Profile '{}' not found!".format(token))
    pass


def profile_interactive_select():
    composition = {}
    for kind in pvConfig.CONFIG_BLOCKS:
        log.print_section("Pick up a {}".format(kind.capitalize()))
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
            log.print_item("{}: {}".format(i + 1, cell))
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
        log.err("A profile named '{}' already exist!".format(
            pf.full_name))

    pf_blocks = {}

    if clone is not None:
        (c_scope, c_label) = pvProfile.extract_profile_from_token(clone)
        base = pvProfile.Profile(c_label, c_scope)
        pf.clone(base)
        pass
    elif interactive:
        log.print_header("profile view (build)")
        pf_blocks = profile_interactive_select()
        pf.fill(pf_blocks)
    else:
        for block in blocks:
            (b_sc, b_kind, b_label) = pvConfig.extract_config_from_token(block)
            cur = pvConfig.ConfigurationBlock(b_kind, b_label, b_sc)
            if cur.is_found() and b_kind not in pf_blocks.keys():
                pf_blocks[b_kind] = cur
            else:
                log.err("Issue with '{}'".format(block))
                if not cur.is_found():
                    raise click.BadOptionUsage("-b", "Such configuration does not exist!")
                else:
                    raise click.BadOptionUsage("-b", "\n".join([ 
                        "'{}' kind is set twice".format(b_kind.upper()),
                        "First is '{}'".format(pf_blocks[b_kind].full_name)
                    ]))
                log.err("")
        pf.fill(pf_blocks)

    log.print_header("profile view")
    pf.flush_to_disk()
    # pf.display()

    log.print_section("final profile (registered as {})".format(pf.scope))
    for k, v in pf_blocks.items():
        log.print_item("{: >9s}: {}".format(
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
            log.err("err")
        else:
            pf.delete()
    else:
        raise click.BadArgumentUsage("Profile '{}' not found!".format(label),
                                     "Please check the 'list' command")


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
            raise click.BadArgumentUsage('Wrongly formatted profile token')
        else:
            pf.open_editor(editor)
    else:
        raise click.BadArgumentUsage("Profile '{}' not found!".format(label),
                               "Please check the 'list' command")


@profile.command(name="update",
                 short_help="Update an existing profile with a given config/file")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.option("-f", "--file", "file", envvar="FROMFILE", show_envvar=True,
              default=None, type=str,
              help="File to use in place of a config. block")
@click.pass_context
def profile_update(ctx, token, editor):
    (scope, label) = pvProfile.extract_profile_from_token(token)
    pf = pvProfile.Profile(label, scope)
    log.nimpl()
    if pf.is_found():
        if pf.scope == 'global' and label == 'local':
            log.err("err")
        else:
            pf.open_editor(editor)
    else:
        log.err("Profile '{}' not found!".format(label),
                "Please check the 'list' command")


@profile.command(name="import",
                 short_help="Import a file as a profile")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.argument("src_file", type=click.File('r'))
@click.pass_context
def profile_import(ctx, token, src_file):
    (scope, label) = pvProfile.extract_profile_from_token(token)
    pf = pvProfile.Profile(label, scope)
    if not pf.is_found():
        pf.fill(yaml.load(src_file.read(), Loader=yaml.Loader))
        pf.flush_to_disk()
    else:
        log.err("Cannot import into an already created profile!")

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

@profile.command(name="split",
                 short_help="Recreate conf. blocks based on a profile")
@click.argument("token", nargs=1, type=click.STRING,
                autocompletion=compl_list_token)
@click.option("-n", "--name", "name", default="default",
              help="name of the basic block to create (should not exist!)"
        )
@click.option("-b", "--block", "block_opt", nargs=1, type=click.STRING,
            help="Re-build only a profile subset", default="all")
@click.option("-s", "--scope", "scope",
              type=click.Choice(io.storage_order()), default=None,
              help="Default scope to store the split (default: same as profile)")
@click.pass_context
def profile_decompose_profile(ctx, token, name, block_opt, scope):
    (p_scope, p_label) = pvProfile.extract_profile_from_token(token)

    blocks = [e.strip() for e in block_opt.split(',')]
    for b in blocks:
        if b == 'all':
            blocks = pvConfig.CONFIG_BLOCKS
            break
        if b not in pvConfig.CONFIG_BLOCKS:
            raise click.BadOptionUsage("--block", "{} is not a valid component.".format(b))

    pf = pvProfile.Profile(p_label, p_scope)
    if not pf.is_found():
        click.BadArgumentUsage("Cannot decompose an non-existent profile: '{}'".format(token))
    else:
        pf.load_from_disk()


    log.print_section('"Create the subsequent configuration blocks:')
    for c in pf.split_into_configs(name, blocks, scope):
        log.print_item(c.full_name)
        c.flush_to_disk()




