import click
from pcvsrt import utils


@click.group(name="profile", short_help="profile")
@click.option("-s", "--scope", "scope",
              type=click.Choice(['global', 'user', 'local'],
                                case_sensitive=False),
              help="Scope where this command applies")
@click.pass_context
def profile(ctx, scope):
    pass


@profile.command(name="list",
                 short_help="List available profiles")
@click.pass_context
def profile_list(ctx):
    pass


@profile.command(name="show",
                 short_help="Prints single profile details")
@click.argument("name", type=str)
@click.pass_context
def profile_show(ctx, name):
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
    if not force:
        if not click.confirm("Are you sure to delete '{}' ?".format(name)):
            return

    print("deleted")
    pass


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
    pass


@profile.command(name="export",
                 short_help="Export a profile to a file")
@click.argument("name", type=str)
@click.argument("dest_file", type=click.File('w'))
@click.pass_context
def profile_export(ctx, name, dest_file):
    pass
