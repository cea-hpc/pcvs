import click
import yaml
import os
import pcvsrt
from pcvsrt import utils, profile
from pcvsrt.utils import logs


@click.group(name="profile", short_help="profile")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="Scope where this command applies")
@click.pass_context
def profile(ctx, scope):
    ctx.obj['scope'] = scope.lower() if scope is not None else None


@profile.command(name="list",
                 short_help="List available profiles")
@click.pass_context
def profile_list(ctx):
    logs.print_header("Profile View")
    scope = ctx.obj['scope']
    profiles = pcvsrt.profile.list_profiles(scope)
    if not profiles:
        logs.print_item("None")
        return
    elif scope is None:  # if no scope has been provided by the user
        for sc in pcvsrt.profile.scope_order():
            # aggregate names for each sccope
            names = [elt[0] for elt in [array for array in profiles[sc]]]
            if not names:
                logs.print_item("{: <6s}: {}None".format(sc.upper(),
                                                         logs.cl('grey')))
            else:
                logs.print_item("{: <6s}: {}".format(sc.upper(),
                                                     ", ".join(names)))
    else:
        names = [x[0] for x in profiles]
        logs.print_item("{: <6s}: {}".format(scope.upper(), ", ".join(names)))
    
    # in case verbosity is enabled, add scope paths
    logs.info("Scopes are labeled as follows:")
    for scope, prefix in pcvsrt.profile.PROFILE_STORAGES.items():
        logs.info("- {}: {}".format(scope.upper(), prefix))


@profile.command(name="show",
                 short_help="Prints single profile details")
@click.argument("name", type=str)
@click.pass_context
def profile_show(ctx, name):
    pf = pcvsrt.profile.Profile(name, ctx.obj['scope'])
    pf.load_from_disk()
    pf.display()
    pass


@profile.command(name="create",
                 short_help="Create/Clone a profile")
@click.argument("name", type=str)
@click.option("-f", "--from", "other",
              default=None, type=str,
              help="Another profile to herit from.")
@click.pass_context
def profile_create(ctx, name, other):
    pass


@profile.command(name="destroy",
                 short_help="Delete a profile from disk")
@click.option("-f", "--force", "force",
              is_flag=True, default=False,
              help="Do not ask for confirmation")
@click.argument("name", type=str)
@click.pass_context
def profile_destroy(ctx, name, force):
    pf = pcvsrt.profile.Profile(name, ctx.obj['scope'])
    if pf.is_found():
        if not force:
            if not click.confirm("Are you sure to delete '{}' ({}) ?".format(name, pf.scope)):
                return
        pf.delete()
    else:
        logs.err("Profile '{}' not found!".format(name), "Please check the 'list' command", abort=1)


@profile.command(name="alter",
                 short_help="Edit an existing profile")
@click.argument("name", type=str)
@click.option("-e", "--editor", "editor",
              default=None, type=str,
              help="Open file with EDITOR")
@click.pass_context
def profile_alter(ctx, name, editor):
    pass


@profile.command(name="import",
                 short_help="Import a file as a profile")
@click.argument("name", type=str)
@click.argument("src_file", type=click.File('r'))
@click.pass_context
def profile_import(ctx, name, src_file):
    pf = pcvsrt.profile.Profile(name, ctx.obj['scope'])
    if pf.is_found():
        pf.fill(yaml.load(src_file.read(), Loader=yaml.Loader))
        pf.flush_to_disk()


@profile.command(name="export",
                 short_help="Export a profile to a file")
@click.argument("name", type=str)
@click.argument("dest_file", type=click.File('w'))
@click.pass_context
def profile_export(ctx, name, dest_file):
    pf = pcvsrt.profile.Profile(name, ctx.obj['scope'])
    if pf.is_found():
        dest_file.write(yaml.dump(pf.dump()))
