import os

import click
from pcvsrt.cli.bank import backend as pvBank
from pcvsrt.helpers import log, io


def compl_list_banks(ctx, args, incomplete):
    pvBank.init()
    array = list()
    for k, v in pvBank.BANKS.items():
        array.append((k,v))
    return [elt for elt in array if incomplete in elt[0]]


@click.group(name="bank", short_help="Manage validation repositories")
@click.pass_context
def bank(ctx):
    pass


@bank.command(name="list", short_help="List available repositories")
@click.argument("name", nargs=1, required=False, type=str,
                autocompletion=compl_list_banks)
@click.pass_context
def bank_list(ctx, name):
    log.print_header("Bank View")
    for label, path in pvBank.list_banks().items():
        log.print_item("{: <8s}: {}".format(label.upper(), path))


@bank.command(name="show", short_help="Display bank's content")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.pass_context
def bank_show(ctx, name):

    log.print_header("Bank View")
    
    b = pvBank.Bank(name)
    if not b.exists():
        log.err("'{}' does not exist".format(name))
    else:
        b.show()



@bank.command(name="create", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("path", nargs=1, type=click.Path(exists=True, file_okay=False), required=True)
@click.pass_context
def bank_create(ctx, name, path):

    log.print_header("Bank View")
    if path is None:
        path = os.getcwd()
    
    path = os.path.abspath(path)

    b = pvBank.Bank(name, path)
    if b.exists():
        log.err("'{}' already exist".format(name))
    else:
        b.register()
        pvBank.flush_to_disk()

@bank.command(name="destroy", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.confirmation_option(
    "-f", "--force", "force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def bank_destroy(ctx, name):

    log.print_header("Bank View")
    b = pvBank.Bank(name)
    if not b.exists():
        log.err("'{}' does not exist".format(name))
    else:
        b.unregister()
        pvBank.flush_to_disk()


@bank.command(name="save", short_help="Save a new object in datastore")
@click.argument("name", nargs=1, required=True, type=str, autocompletion=compl_list_banks)
@click.argument("attr", nargs=1, required=True)
@click.argument("obj", nargs=1, required=True)
@click.pass_context
def bank_save_content(ctx, name, attr, obj):
    bank = pvBank.Bank(name)
    if not bank.exists():
        log.err("Unable to save content into a non-existent bank.",
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
    bank = pvBank.Bank(name)
    if not bank.exists():
        log.err("Unable to load content from a non-existent bank.",
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
    bank = pvBank.Bank(name)
    if not bank.exists():
        log.err("Unable to modify content from a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.delete(attr)
        