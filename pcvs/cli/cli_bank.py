import os

import click

from pcvsrt.backend import bank as pvBank
from pcvsrt.helpers import log


def compl_list_banks(ctx, args, incomplete):
    """bank name completion function"""
    pvBank.init()
    array = list()
    for k, v in pvBank.BANKS.items():
        array.append((k,v))
    return [elt for elt in array if incomplete in elt[0]]


@click.group(name="bank", short_help="Persistent data repository management")
@click.pass_context
def bank(ctx):
    """root function to handle a bank."""
    pass


@bank.command(name="list", short_help="List known repositories")
@click.pass_context
def bank_list(ctx):
    """
    List known repositories, stored under $HOME_STORAGE/banks.yml"""
    log.print_header("Bank View")
    for label, path in pvBank.list_banks().items():
        log.print_item("{: <8s}: {}".format(label.upper(), path))


@bank.command(name="show", short_help="Display data stored in a repo.")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.pass_context
def bank_show(ctx, name):
    """Display all data stored into NAME repository"""
    log.print_header("Bank View")

    b = pvBank.Bank(name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        b.show()


@bank.command(name="create", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("path", nargs=1, type=click.Path(exists=True, file_okay=False), required=True)
@click.pass_context
def bank_create(ctx, name, path):
    """Create a new bank, named NAME, data will be stored under PATH."""
    log.print_header("Bank View")
    if path is None:
        path = os.getcwd()
    
    path = os.path.abspath(path)

    b = pvBank.Bank(name, path)
    if b.exists():
        raise click.BadArgumentUsage("'{}' already exist".format(name))
    else:
        b.register()
        pvBank.flush_to_disk()

@bank.command(name="destroy", short_help="Delete an existing bank")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.confirmation_option(
    "-f", "--force", "force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def bank_destroy(ctx, name):
    """Remove the bank NAME from PCVS management. This does not include
    repository deletion. 'data.yml' and bank entry in the configuratino file
    will be removed but existing data are preserved.
    """
    log.print_header("Bank View")
    b = pvBank.Bank(name)
    if not b.exists():
        raise click.BadArgumentUsage("'{}' does not exist".format(name))
    else:
        b.unregister()
        pvBank.flush_to_disk()


@bank.command(name="save", short_help="Store an object to the datastore")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("attr", nargs=1, required=True)
@click.argument("obj", nargs=1, required=True)
@click.pass_context
def bank_save_content(ctx, name, attr, obj):
    """Save an object OBJ (currently only filepaths) under ATTR label into the
    previously-registered bank NAME"""
    bank = pvBank.Bank(name)
    if not bank.exists():
        raise click.BadArgumentUsage("Unable to save content into a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.save(attr, obj)


@bank.command(name="load", short_help="Load an object from datastore")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("attr", nargs=1, required=True)
@click.option("-d", "--dest", "dest", default=None,
              type=click.Path(file_okay=False),
              help="Directory where extracting saved objects")
@click.pass_context
def bank_load_content(ctx, name, attr, dest):
    """Load  any object under ATTR label from the previously-registered bank
    NAME"""
    bank = pvBank.Bank(name)
    if not bank.exists():
        raise click.BadArgumentUsage("Unable to load content from a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.load(attr, dest)


@bank.command(name="delete", short_help="delete an object from datastore")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("attr", nargs=1, required=True)
@click.confirmation_option(
    "-f", "--force", "force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def bank_delete_content(ctx, name, attr):
    """Delete anyobject under ATTR label from the previously-registered bank NAME"""
    bank = pvBank.Bank(name)
    if not bank.exists():
        raise click.BadArgumentUsage("Unable to modify content from a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.delete(attr)
