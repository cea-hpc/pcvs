import os
import sys

from click.shell_completion import CompletionItem

from pcvs import io
from pcvs.backend import bank as pvBank
from pcvs.helpers import utils

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click


def compl_list_banks(ctx, args, incomplete):
    """bank name completion function.

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """
    pvBank.init()
    array = list()
    for k, v in pvBank.BANKS.items():
        array.append((k, v))
    return [CompletionItem(elt[0], help=elt[1]) for elt in array if incomplete in elt[0]]


def compl_bank_projects(ctx, args, incomplete):
    """bank project completion function.

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """
    pvBank.init()
    array = list()
    for bankname, bankpath in compl_list_banks(None, None, ''):
        bank = pvBank.Bank(token=bankname)
        bank.connect()
        for project in bank.list_projects():
            array.append((bankname + "@" + project, bankpath))
        bank.disconnect()

    return [CompletionItem(elt[0], help=elt[1]) for elt in array if incomplete in elt[0]]


@click.group(name="bank", short_help="Persistent data repository management")
@click.pass_context
def bank(ctx):
    """Bank entry-point."""
    pass


@bank.command(name="list", short_help="List known repositories")
@click.pass_context
def bank_list(ctx):
    """List known repositories, stored under ``PATH_BANK``."""
    io.console.print_header("Bank View")
    for label, path in pvBank.list_banks().items():
        io.console.print_item("{:<8}: {}".format(label.upper(), path))


@bank.command(name="show", short_help="Display data stored in a repo.")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.option("-p", "--path", "path", is_flag=True, default=False,
              help="Display bank location")
@click.pass_context
def bank_show(ctx, name, path):
    """Display all data stored into NAME repository"""
    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        b.connect()
    
    if path:
        print(b.path)
    else:
        io.console.print_header("Bank View")
        b.show()


@bank.command(name="init", short_help="Register a bank & create a repo if needed")
@click.argument("name", type=str, shell_complete=compl_list_banks)
@click.argument("path", required=False, type=click.Path(exists=False, file_okay=False))
@click.pass_context
def bank_create(ctx, name, path):
    """Create a new bank, named NAME, data will be stored under PATH."""
    io.console.print_header("Bank View")
    if path is None:
        path = os.getcwd()

    path = os.path.abspath(path)

    b = pvBank.Bank(path, token=name)
    if b.exists():
        raise click.BadArgumentUsage("'{}' already exist".format(name))
    else:
        b.connect()
        b.save_to_global()


@bank.command(name="destroy", short_help="Delete an existing bank")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.option("-s", "--symlink", is_flag=True,
              help="Only delete the HOME symbolic link (keep data intact)")
@click.confirmation_option(
    "-f", "--force", "force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def bank_destroy(ctx, name, symlink):
    """Remove the bank NAME from PCVS management. This does not include
    repository deletion. 'data.yml' and bank entry in the configuratino file
    will be removed but existing data are preserved.
    """
    io.console.print_header("Bank View")
    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        if not symlink:
            io.console.warn(
                "To delete a bank, just remove the directory {}".format(b.prefix))
        io.console.print_item("Bank '{}' unlinked".format(name))
        pvBank.rm_banklink(name)


@bank.command(name="save", short_help="Save a new run to the datastore")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.argument("path", nargs=1, required=True, type=click.Path(exists=True))
@click.option('--message', "-m", "msg", default=None,
              help="Use a custom Run() message")
@click.pass_context
def bank_save_run(ctx, name, path, msg):
    """Create a backup from a previously generated build directory. NAME will be
    the target bank name, PATH the build directory"""

    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))

    path = os.path.abspath(path)
    project = b.default_project

    b.connect()
    if os.path.isfile(path):
        b.save_from_archive(project, path, msg=msg)
    elif os.path.isdir(path):
        path = utils.find_buildir_from_prefix(path)
        b.save_from_buildir(project, path, msg=msg)


@bank.command(name="load", short_help="Extract infos from the datastore")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.option("--since", "start", default=None,
              help="Select a starting point from where data will be extracted")
@click.option("--until", "end", default=None,
              help="Select the last date (included) where data will be searched for")
@click.option("-s", "--startswith", "prefix",
              type=str, default="",
              help="Select only a subset of each runs based on provided prefix")
@click.pass_context
def bank_load(ctx, name, prefix, start, end):
    b = pvBank.Bank(token=name)
    serie = b.get_serie()
    run = serie.last
    data = []
    from rich.progress import Progress
    with Progress():
        if not prefix:
            for j in run.jobs:
                data.append(j.to_json())
        else:
            for j in run.get_data(prefix):
                data.append(j.to_json())
    import json
    print(json.dumps(data))


@bank.command(name="extract", short_help="Extract infos from the datastore")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.argument("key", nargs=1, required=True)
@click.pass_context
def bank_extract(ctx, name, key):

    pass
