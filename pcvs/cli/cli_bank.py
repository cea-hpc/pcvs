import os

from click.shell_completion import CompletionItem

from pcvs import io
from pcvs.backend import bank as pvBank
from pcvs.dsl import Job
from pcvs.helpers import utils

try:
    import rich_click as click

    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click  # type: ignore


def compl_list_banks(
    ctx: click.Context, param: click.Parameter, incomplete: str  # pylint: disable=unused-argument
) -> list[CompletionItem]:
    """
    Bank name completion function.

    :param ctx: Click context
    :param param: the option/argument requesting completion.
    :param incomplete: the user input
    :return: the completed argument.
    """
    array = []
    for k, v in pvBank.list_banks().items():
        array.append((k, v))
    return [CompletionItem(elt[0], help=elt[1]) for elt in array if incomplete in elt[0]]


def compl_bank_projects(
    ctx: click.Context, param: click.Parameter, incomplete: str  # pylint: disable=unused-argument
) -> list[CompletionItem]:
    """
    Bank project completion function.

    :param ctx: Click context
    :param param: the option/argument requesting completion.
    :param incomplete: the user input
    :return: the completed argument.
    """
    array = []
    for completion in compl_list_banks(ctx, param, ""):
        bankname, bankpath = completion.value, completion.help
        result_bank = pvBank.Bank(token=bankname)
        result_bank.connect()
        for project in result_bank.list_projects():
            array.append((bankname + "@" + project, bankpath))
        result_bank.disconnect()

    return [CompletionItem(elt[0], help=elt[1]) for elt in array if incomplete in elt[0]]


@click.group(
    name="bank",
    short_help="Persistent data repository management",
)
@click.pass_context
def cli_bank(ctx: click.Context) -> None:  # pylint: disable=unused-argument
    """Bank entry-point."""


@cli_bank.command(
    name="list",
    short_help="List known repositories",
)
@click.pass_context
def cli_bank_list(ctx: click.Context) -> None:  # pylint: disable=unused-argument
    """List known repositories, stored under ``PATH_BANK``."""
    io.console.print_header("Bank List")
    for label, path in pvBank.list_banks().items():
        io.console.print_item(f"{label}: {path}")


@cli_bank.command(
    name="show",
    short_help="Display data stored in a repo.",
)
@click.argument(
    "name",
    nargs=1,
    required=True,
    type=str,
    shell_complete=compl_list_banks,
)
@click.option(
    "-p",
    "--path",
    "is_path",
    is_flag=True,
    default=False,
    help="Display bank location",
)
@click.pass_context
def cli_bank_show(
    ctx: click.Context, name: str, is_path: bool  # pylint: disable=unused-argument
) -> None:
    """Display all data stored into NAME repository"""
    b = pvBank.Bank(token=name)
    b.connect()

    if is_path:
        print(b.path)
    else:
        io.console.print_header("Bank Show")
        b.show()


@cli_bank.command(
    name="init",
    short_help="Register a bank & create a repo if needed",
)
@click.argument(
    "name",
    type=str,
    shell_complete=compl_list_banks,
)
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=False, file_okay=False),
)
@click.pass_context
def cli_bank_init(
    ctx: click.Context, name: str, path: str | None  # pylint: disable=unused-argument
) -> None:
    """Create a new bank, named NAME, data will be stored under PATH."""
    io.console.print_header("Bank Init")
    if path is None:
        path = os.path.join(os.getcwd(), name)
    path = os.path.abspath(path)

    if not pvBank.init_banklink(name, path):
        raise click.BadArgumentUsage(f"'{name}' already exist or can't be created")


@cli_bank.command(
    name="destroy",
    short_help="Delete an existing bank",
)
@click.argument(
    "name",
    nargs=1,
    required=True,
    type=str,
    shell_complete=compl_list_banks,
    # help="The name of the bank to delete",
)
@click.option(
    "-s",
    "--symlink",
    is_flag=True,
    help="Only delete the HOME symbolic link (keep data intact)",
)
@click.confirmation_option(
    "-f",
    "--force",
    "force",
    prompt="Are your sure to delete repository and its content ?",
    help="Do not ask for confirmation before deletion",
)
@click.pass_context
def cli_bank_destroy(
    ctx: click.Context, name: str, symlink: bool  # pylint: disable=unused-argument
) -> None:
    """
    Remove the bank NAME from PCVS management. This does not include repository deletion.

    'data.yml' and bank entry in the configuration file will be removed but existing data are preserved.
    """
    io.console.print_header("Bank Destroy")
    b = pvBank.Bank(token=name)
    if not symlink:
        io.console.warn("To delete a bank, just remove the directory {}".format(b.prefix))
    io.console.print_item("Bank '{}' unlinked".format(name))
    pvBank.rm_banklink(name)


@cli_bank.command(
    name="save",
    short_help="Save a new run to the datastore",
)
@click.argument(
    "name",
    nargs=1,
    required=True,
    type=str,
    shell_complete=compl_list_banks,
    # help="The bank to save the run to.",
)
@click.argument(
    "path",
    nargs=1,
    required=True,
    type=click.Path(exists=True),
    # help="The path to the build directory.",
)
@click.option(
    "--message",
    "-m",
    "msg",
    default=None,
    help="Use a custom commit message",
)
@click.pass_context
def cli_bank_save_run(
    ctx: click.Context, name: str, path: str, msg: str | None  # pylint: disable=unused-argument
) -> None:
    """Create a backup from a previously generated build directory."""
    b = pvBank.Bank(token=name)
    path = os.path.abspath(path)
    project = b.default_project

    b.connect()
    if os.path.isfile(path):
        b.save_from_archive(project, path, msg=msg)
    elif os.path.isdir(path):
        path = utils.find_buildir_from_prefix(path)
        b.save_from_buildir(project, path, msg=msg)


@cli_bank.command(
    name="load",
    short_help="Extract infos from the datastore",
)
@click.argument(
    "name",
    nargs=1,
    required=True,
    type=str,
    shell_complete=compl_list_banks,
    # help="The name of the project@bank to load the tests from.",
)
@click.option(
    "-s",
    "--startswith",
    "prefix",
    type=str,
    default="",
    help="Select only a subset of each runs based on provided prefix",
)
@click.pass_context
def cli_bank_load(
    ctx: click.Context, name: str, prefix: str  # pylint: disable=unused-argument
) -> None:
    """Load a bank."""
    b = pvBank.Bank(token=name)
    series = b.get_series()
    assert series is not None
    run = series.last
    assert run is not None
    data = []
    from rich.progress import Progress

    with Progress():
        if not prefix:
            for j in run.jobs:
                data.append(j.to_json())
        else:
            job: Job | None = run.get_data(prefix)
            assert job is not None
            data.append(job.to_json())
    import json

    print(json.dumps(data))
