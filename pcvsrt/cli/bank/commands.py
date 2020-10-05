import os

import click
from pcvsrt.cli.bank import backend as pvBank
from pcvsrt.helpers import log, io


def compl_list_banks(ctx, args, incomplete):
    pvBank.init()
    flat_array = []
    for elt in pvBank.BANKS:
        flat_array.append(elt[0])
    return [elt for elt in flat_array if incomplete in elt]


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


@bank.command(name="create", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str)
@click.argument("path", nargs=1, type=click.Path(exists=True, file_okay=False), required=True)
@click.option("-f", "--force", "force", default=False, is_flag=True)
@click.pass_context
def bank_create(ctx, name, path, force):

    log.print_header("Bank View")
    if path is None:
        path = os.getcwd()

    b = pvBank.Bank(name, path)
    if b.exists() and not force:
        log.err("'{}' already exist, use '-f' to overwrite".format(name))
    else:
        b.save()
        pvBank.flush_to_disk()

@bank.command(name="destroy", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str)
@click.confirmation_option(
    "-f", "--force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion")
@click.pass_context
def bank_destroy(ctx, name, force):

    log.print_header("Bank View")
    if path is None:
        path = os.getcwd()

    b = pvBank.Bank(name, path)
    if b.exists() and not force:
        log.err("'{}' already exist, use '-f' to overwrite".format(name))
    else:
        b.save()
        pvBank.flush_to_disk()


@bank.command(name="push", short_help="Push a new object in datastore")
@click.argument("name", nargs=1, required=True, type=str)
@click.argument("attr", nargs=1, required=True)
@click.argument("object", nargs=1, required=True)
@click.pass_context
def bank_push_content(ctx, name, attr, obj):
    bank = pvBank.Bank(name)
    if not bank.exists():
        log.err("Unable to push content to a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.save(attr, obj)


@bank.command(name="push", short_help="Push a new object in datastore")
@click.argument("name", nargs=1, required=True, type=str)
@click.argument("attr", nargs=1, required=True)
@click.pass_context
def bank_push_content(ctx, name, attr):
    bank = pvBank.Bank(name)
    if not bank.exists():
        log.err("Unable to push content to a non-existent bank.",
                "Please use the 'create' command first.")
    else:
        bank.load(attr)