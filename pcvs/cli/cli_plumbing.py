import sys

from pcvs.backend.bank import Bank
from pcvs.cli.cli_bank import compl_list_banks
from pcvs.dsl.analysis import ResolverAnalysis
from pcvs.helpers.system import MetaConfig

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click


@click.command(name="resolve", short_help="Resolve test status")
@click.option("-b", "--bank", "bankname", shell_complete=compl_list_banks,
              default=None, help="explicit bank name to use.")
@click.option("-f", "--file", "file",
              type=click.Path(exists=False), default=None,
              is_flag=False, help="read from file instead of stdin")
@click.pass_context
def resolve(ctx, file, bankname):

    if file:
        with open(file, 'r') as fh:
            stream = fh.read().rstrip()
    else:
        stream = sys.stdin.read().rstrip()

    if not bankname:
        bankname = MetaConfig.root.validation.target_bank

    # may deadlock !!
    bank = Bank(bankname)

    print(stream)

    bank.disconnect()
