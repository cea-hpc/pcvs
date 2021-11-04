import os

import click

from pcvs.backend import bank as pvBank
from pcvs.helpers import log, utils
from pcvs.helpers.exceptions import BankException


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
    return [elt for elt in array if incomplete in elt[0]]


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
        bank.connect_repository()
        for project in bank.list_projects():
            array.append((bankname + "@" + project, bankpath))

    return [elt for elt in array if incomplete in elt[0]]


@click.group(name="bank", short_help="Persistent data repository management")
@click.pass_context
def bank(ctx):
    """Bank entry-point."""
    pass


@bank.command(name="list", short_help="List known repositories")
@click.pass_context
def bank_list(ctx):
    """List known repositories, stored under ``PATH_BANK``."""
    log.manager.print_header("Bank View")
    for label, path in pvBank.list_banks().items():
        log.manager.print_item("{:<8}: {}".format(label.upper(), path))


@bank.command(name="show", short_help="Display data stored in a repo.")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.pass_context
def bank_show(ctx, name):
    """Display all data stored into NAME repository"""
    log.manager.print_header("Bank View")

    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        b.connect_repository()
        b.show()


@bank.command(name="init", short_help="Register a bank & create a repo if needed")
@click.argument("name", type=str, shell_complete=compl_list_banks)
@click.argument("path", required=False, type=click.Path(exists=False, file_okay=False))
@click.pass_context
def bank_create(ctx, name, path):
    """Create a new bank, named NAME, data will be stored under PATH."""
    log.manager.print_header("Bank View")
    if path is None:
        path = os.getcwd()

    path = os.path.abspath(path)

    b = pvBank.Bank(path, token=name)
    if b.exists():
        raise click.BadArgumentUsage("'{}' already exist".format(name))
    else:
        b.connect_repository()
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
    log.manager.print_header("Bank View")
    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        if not symlink:
            log.manager.warn(
                "To delete a bank, just remove the directory {}".format(b.prefix))
        log.manager.print_item("Bank '{}' unlinked".format(name))
        pvBank.rm_banklink(name)


@bank.command(name="save", short_help="Save a new run to the datastore")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.argument("path", nargs=1, required=True, type=click.Path(exists=True))
@click.pass_context
def bank_save_run(ctx, name, path):
    """Create a backup from a previously generated build directory. NAME will be
    the target bank name, PATH the build directory"""

    b = pvBank.Bank(token=name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))

    path = os.path.abspath(path)
    project = b.preferred_proj

    b.connect_repository()
    if os.path.isfile(path):
        b.save_from_archive(project, path)
    elif os.path.isdir(path):
        path = utils.find_buildir_from_prefix(path)
        b.save_from_buildir(project, path)


@bank.command(name="load", short_help="Extract infos from the datastore")
@click.argument("name", nargs=1, required=True, type=str, shell_complete=compl_list_banks)
@click.argument("key", nargs=1, required=True)
@click.option("--since", "start", default=None,
              help="Select a starting point from where data will be extracted")
@click.option("--until", "end", default=None,
              help="Select the last date (included) where data will be searched for")
@click.option("-f", "--format", "format",
              type=click.Choice(['json', 'list']), default='json',
              help="Request a set of values from a given key")
@click.pass_context
def bank_load(ctx, name, key, format, start, end):

    b = pvBank.Bank(token=name)
    raise BankException.WIPError("bank load")
    try:
        b.connect_repository()
        b.extract_data(key, start, end, format)
    except NotExist:
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    except KeyError:
        raise click.BadArgumentUsage(
            "The key \'{}\' is not valid within {} scope".format(key, name))
