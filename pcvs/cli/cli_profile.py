import os
import sys

import click
from ruamel.yaml import YAML

from pcvs import PATH_INSTDIR
from pcvs.backend import config as pvConfig
from pcvs.backend import profile as pvProfile
from pcvs.cli import cli_config
from pcvs.helpers import log, utils
from pcvs.helpers.exceptions import ProfileException, ValidationException


def compl_list_token(ctx, args, incomplete):  # pragma: no cover
    """profile name completion function.

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """
    pvProfile.init()
    flat_array = []
    for scope in utils.storage_order():
        for elt in pvProfile.PROFILE_EXISTING[scope]:
            flat_array.append(scope + "." + elt[0])

    return [elt for elt in flat_array if incomplete in elt]


def compl_list_templates(ctx, args, incomplete):  # pragma: no cover
    """ the profile template completion. 

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """
    return [name for name, path in pvProfile.list_templates() if incomplete in name]


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
                type=click.STRING, shell_complete=compl_list_token)
@click.option("-a", "--all", "all", is_flag=True, default=False,
              help="Include any extra resources for profile (templates, etc.)")
@click.pass_context
def profile_list(ctx, token, all):
    """
    List all known profiles to be used as part of a validation process. The
    list can be filtered out depending on the '--scope' option to only print
    out profiles available at a given granularity.
    """
    (scope, label) = (None, None)
    if token:
        (scope, _, label) = utils.extract_infos_from_token(token, single="left",
                                                           maxsplit=2)

    if label:
        log.manager.warn("no LABEL required for this command")

    utils.check_valid_scope(scope)

    log.manager.print_header("Profile View")
    profiles = pvProfile.list_profiles(scope)
    if not profiles:
        log.manager.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in utils.storage_order():
            # aggregate names for each sccope
            names = sorted([elt[0]
                            for elt in [array for array in profiles[sc]]])
            if not names:
                log.manager.print_item("{: <6s}: {}".format(sc.upper(),
                                                            log.manager.style('None',
                                                                              fg='bright_black')))
            else:
                log.manager.print_item("{: <6s}: {}".format(sc.upper(),
                                                            ", ".join(names)))
    else:
        names = sorted([x[0] for x in profiles])
        log.manager.print_item("{: <6s}: {}".format(
            scope.upper(), ", ".join(names)))

    if all:
        log.manager.print_section(
            "Available templates to create from (--base option):")
        log.manager.print_item(
            ", ".join([x[0] for x in pvProfile.list_templates()]))

    # in case verbosity is enabled, add scope paths
    log.manager.info("Scopes are ordered as follows:")
    for i, scope in enumerate(utils.storage_order()):
        log.manager.info("{}. {}: {}".format(
            i+1, scope.upper(), utils.STORAGES[scope]))


@profile.command(name="show",
                 short_help="Prints single profile details")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.pass_context
def profile_show(ctx, token):
    """Prints a detailed view of the NAME profile."""
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)
    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        pf.load_from_disk()
        pf.display()
    else:
        raise click.BadArgumentUsage("Profile '{}' not found!".format(token))
    pass


def profile_interactive_select():
    """Interactive selection of config blocks to build a profile.

    Based on user input, this function displays, for each kind, possible blocks
    and waits for a selection. A final profile is built from them.

    :return: concatenation of basic blokcs
    :rtype: dict
    """
    composition = {}
    for kind in pvConfig.CONFIG_BLOCKS:
        log.manager.print_section("Pick up a {}".format(kind.capitalize()))
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
            log.manager.print_item("{}: {}".format(i + 1, cell))
        while idx < 0 or len(choices) <= idx:
            idx = click.prompt("Your selection", default, type=int) - 1
        (scope, _, label) = utils.extract_infos_from_token(
            choices[idx], pair="span")
        composition[kind] = pvConfig.ConfigurationBlock(kind, label, scope)

    return composition


@profile.command(name="create",
                 short_help="Build/copy a profile from basic conf blocks")
@click.option("-i", "--interactive", "interactive", show_envvar=True,
              default=False, is_flag=True,
              help="Build the profile by interactively selecting conf. blocks")
@click.option("-b", "--block", "blocks", multiple=True,
              default=None, show_envvar=True,
              shell_complete=cli_config.compl_list_token,
              help="non-interactive option to build a profile")
@click.option("-c", "--clone", "clone", show_envvar=True,
              default=None, type=click.STRING,
              shell_complete=compl_list_token,
              help="Another profile to herit from.")
@click.option("-t", "--base", "base", type=str, default=None,
              shell_complete=compl_list_templates,
              help="Select a template profile to herit from")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.pass_context
def profile_create(ctx, token, interactive, blocks, clone, base):
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
    if clone and base:
        raise click.BadOptionUsage(
            "--base/--clone", "Cannot use --base & --clone simultaneously.")

    (p_scope, _, p_label) = utils.extract_infos_from_token(token, maxsplit=2)

    pf = pvProfile.Profile(p_label, p_scope)
    if pf.is_found():
        raise click.BadArgumentUsage("Profile named '{}' already exist!".format(
            pf.full_name))

    pf_blocks = {}

    if clone is not None:
        (c_scope, _, c_label) = utils.extract_infos_from_token(clone, maxsplit=2)
        base = pvProfile.Profile(c_label, c_scope)
        base.load_from_disk()
        pf.clone(base)
    elif base:
        pf.load_template(base)
    elif interactive:
        log.manager.print_header("profile view (build)")
        pf_blocks = profile_interactive_select()
        pf.fill(pf_blocks)
    else:
        if len(blocks) > 0:
            for blocklist in blocks:
                for block in blocklist.split(','):
                    (b_sc, b_kind, b_label) = utils.extract_infos_from_token(block)
                    cur = pvConfig.ConfigurationBlock(b_kind, b_label, b_sc)
                    if not cur.is_found():
                        raise click.BadOptionUsage(
                            "--block", "'{}' config block does not exist".format(block))
                    elif b_kind in pf_blocks.keys():
                        raise click.BadOptionUsage(
                            "--block", "'{}' config block set twice".format(b_kind))
                    pf_blocks[b_kind] = cur
            pf.fill(pf_blocks)
        else:
            base = pvProfile.Profile('default', None)
            base.load_template()
            pf.clone(base)

    log.manager.print_header("profile view")
    pf.flush_to_disk()
    # pf.display()

    log.manager.print_section(
        "final profile (registered as {})".format(pf.scope))
    for k, v in pf_blocks.items():
        log.manager.print_item("{: >9s}: {}".format(
            k.upper(), ".".join([v.scope, v.short_name])))


@profile.command(name="destroy",
                 short_help="Delete a profile from disk")
@click.confirmation_option(
    "-f", "--force", "force", expose_value=False,
    prompt="Are you sure you want to delete this profile ?",
    help="Do not ask for confirmation")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.pass_context
def profile_destroy(ctx, token):
    """Delete an existing profile named TOKEN.

    Use with caution, this action is irreversible !
    """
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)

    # tricky case, avoid users to use reserved word for scopes as
    # profile label unless they explicitly specify a scope !
    # 'local.global' is allowed, 'global' isn't
    if scope is None and label in utils.storage_order():
        raise click.BadArgumentUsage("token is ambiguous. Please specify")

    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        pf.delete()
    else:
        raise click.BadArgumentUsage(
            "Profile '{}' not found! Please check the 'list' command".format(label),)


@profile.command(name="edit",
                 short_help="Edit an existing profile")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.option("-p", "--edit-plugin", "edit_plugin", is_flag=True, default=False,
              help="Only edit the plugin code ('runtime')")
@click.option("-e", "--editor", "editor", envvar="EDITOR", show_envvar=True,
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
@log.manager.capture_exception(ValidationException.FormatError)
def profile_edit(ctx, token, editor, edit_plugin):
    """Edit an existing profile with the given EDITOR. The '-p' option will open
    the decoded runtime plugin code stored as a base64 string into the profile
    for edition.

    After edition, the result will be validated to ensure
    coherency. If the test failed a rej*.yml will be created with the edited
    content.
    """
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)
    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        if pf.scope == 'global' and label == 'local':
            raise click.BadArgumentUsage('Wrongly formatted profile token')
        else:
            if edit_plugin:
                pf.edit_plugin(editor)
            else:
                pf.edit(editor)
    else:
        raise click.BadArgumentUsage(
            "\n".join([
                "Profile '{}' not found!\n".format(label),
                "Please check the 'list' command"]))


@profile.command(name="import",
                 short_help="Import a file as a profile")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.option("-s", "--source", "src_file", type=click.File('r'), default=sys.stdin)
@click.option("-f", "--force", "force", is_flag=True, default=False)
@click.pass_context
def profile_import(ctx, token, src_file, force):
    """Create a profile from a file. If the profile name is already used, it
    will not be overwritten unless '--force' is used.
    """
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)
    pf = pvProfile.Profile(label, scope)
    if not pf.is_found() or force:
        pf.fill(YAML(typ='safe').load(src_file.read()))
        pf.flush_to_disk()
    else:
        raise ProfileException.AlreadyExistError("{}".format(pf.full_name))


@profile.command(name="export",
                 short_help="Export a profile to a file")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.option("-o", "--output", "dest_file", type=click.File('w'), default=sys.stdout)
@click.pass_context
def profile_export(ctx, token, dest_file):
    """Export a profile to a YAML. If '--output' is omitted, the standard output
    is used to print the profile."""
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)

    pf = pvProfile.Profile(label, scope)
    if pf.is_found():
        pf.load_from_disk()
        YAML(typ='safe').dump(pf.dump(), dest_file)


@profile.command(name="split",
                 short_help="Recreate conf. blocks based on a profile")
@click.argument("token", nargs=1, type=click.STRING,
                shell_complete=compl_list_token)
@click.option("-n", "--name", "name", default="default",
              help="name of the basic block to create (should not exist!)"
              )
@click.option("-b", "--block", "block_opt", nargs=1, type=click.STRING,
              help="Re-build only a profile subset", default="all")
@click.option("-s", "--scope", "scope",
              type=click.Choice(utils.storage_order()), default=None,
              help="Default scope to store the split (default: same as profile)")
@click.pass_context
def profile_decompose_profile(ctx, token, name, block_opt, scope):
    """Build basic configuration blocks from a given profile. Every block name will
    be prefixed with the '-n' option (set to 'default')
    """
    (scope, _, label) = utils.extract_infos_from_token(token, maxsplit=2)

    blocks = [e.strip() for e in block_opt.split(',')]
    for b in blocks:
        if b == 'all':
            blocks = pvConfig.CONFIG_BLOCKS
            break
        if b not in pvConfig.CONFIG_BLOCKS:
            raise click.BadOptionUsage(
                "--block", "{} is not a valid component.".format(b))

    pf = pvProfile.Profile(label, scope)
    if not pf.is_found():
        click.BadArgumentUsage(
            "Cannot decompose an non-existent profile: '{}'".format(token))
    else:
        pf.load_from_disk()

    log.manager.print_section('"Create the subsequent configuration blocks:')
    for c in pf.split_into_configs(name, blocks, scope):
        log.manager.print_item(c.full_name)
        c.flush_to_disk()
