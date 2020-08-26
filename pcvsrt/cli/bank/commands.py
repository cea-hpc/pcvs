import os

import click
from pcvsrt import bank as pvBank
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


@bank.command(name="list", short_help="Register a new bank")
@click.argument("name", nargs=1, required=False, type=str,
                autocompletion=compl_list_banks)
@click.pass_context
def bank_list(ctx, name):
    log.print_header("Bank View")
    for label, path in pvBank.list_banks().items():
        log.print_item("{: <8s}: {}".format(label.upper(), path))


@bank.command(name="init", short_help="Register a new bank")
@click.argument("name", nargs=1, required=True, type=str)
@click.argument("path", nargs=1, type=click.Path(exists=True, file_okay=False), required=False)
@click.option("-f", "--force", "force", default=False, is_flag=True)
@click.pass_context
def bank_init(ctx, name, path, force):

    log.print_header("Bank View")
    if path is None:
        path = os.getcwd()

    b = pvBank.Bank(name, path)
    if b.exists() and not force:
        log.err("'{}' already exist, use '-f' to overwrite".format(name), abort=1)
    else:
        b.flush_to_disk()

