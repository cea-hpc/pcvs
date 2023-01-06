import os
from datetime import datetime, timedelta

from rich.table import Table

from pcvs import NAME_BUILDFILE, io
from pcvs.backend import session as pvSession
from pcvs.helpers import utils

try:
    import rich_click as click
    click.rich_click.SHOW_ARGUMENTS = True
except ImportError:
    import click

from click.shell_completion import CompletionItem


def compl_session_token(ctx, args, incomplete) -> list:
    """Session name completion function.

    :param ctx: Click context
    :type ctx: :class:`Click.Context`
    :param args: the option/argument requesting completion.
    :type args: str
    :param incomplete: the user input
    :type incomplete: str
    """

    sessions = pvSession.list_alive_sessions()
    if sessions is None:
        return []
    return [CompletionItem(k, help=str(pvSession.Session.State(v['state']))) for k, v in sessions.items() if incomplete in str(k)]


@click.command(name="session", short_help="Manage multiple validations")
@click.option('-c', '--clear', 'ack', type=int, default=None,
              help="Clear a 'completed' remote session, for removing from logs")
@click.option('-C', '--clear-all', 'ack_all', is_flag=True, default=False,
              help="Clear all completed sessions, for removing from logs")
@click.option('-l', '--list', is_flag=True,
              help="List detached sessions")
@click.pass_context
def session(ctx, ack, list, ack_all):
    """Manage sessions by listing or acknowledging their completion."""
    sessions = pvSession.list_alive_sessions()
    if sessions is None:
        sessions = dict()

    if ack_all is True:
        for session_id in sessions.keys():
            if sessions[session_id]['state'] != pvSession.Session.State.IN_PROGRESS:
                pvSession.remove_session_from_file(session_id)
                lockfile = os.path.join(
                    sessions[session_id]['path'], NAME_BUILDFILE)
                utils.unlock_file(lockfile)
    elif ack is not None:
        if ack not in sessions.keys():
            raise click.BadOptionUsage(
                '--ack', "No such Session id (see pcvs session)")
        elif sessions[ack]['state'] not in [pvSession.Session.State.ERROR, pvSession.Session.State.COMPLETED]:
            raise click.BadOptionUsage(
                '--ack', "This session is not completed yet")

        pvSession.remove_session_from_file(ack)
        lockfile = os.path.join(sessions[ack]['path'], NAME_BUILDFILE)
        utils.unlock_file(lockfile)
    else:  # listing is the defualt
        if len(sessions) <= 0:
            io.console.print("[italic bold]No sessions")
            return
        table = Table(title="Sessions", expand=True)
        table.add_column("SID", justify="center", max_width=10)
        table.add_column("Status", justify="right")
        table.add_column("Started", justify="center")
        table.add_column("Elasped", justify="right")
        table.add_column("Location", justify="left")

        for sk, sv in sessions.items():
            s = pvSession.Session()
            s.load_from(sk, sv)
            status = "Broken"
            duration = timedelta()
            line_style = "default"
            if s.state == pvSession.Session.State.IN_PROGRESS:
                duration = datetime.now() - s.property('started')
                status = "{:3.2f} %".format(s.property('progress'))
                line_style = "yellow"
            elif s.state == pvSession.Session.State.COMPLETED:
                duration = s.property('ended') - s.property('started')
                status = "100.00 %"
                line_style = "green bold"
            elif s.state == pvSession.Session.State.WAITING:
                duration = datetime.now() - s.property('started')
                status = "Waiting"
                line_style = "yellow"

            table.add_row("[{}]{:0>6}".format(line_style, s.id),
                          "[{}]{}".format(line_style, status),
                          "[{}]{}".format(line_style, datetime.strftime(
                              s.property("started"),
                              "%Y-%m-%d %H:%M")),
                          "[{}]{}".format("red bold" if duration.days > 0 else line_style,
                                          timedelta(days=duration.days, seconds=duration.seconds)),
                          "[{}]{}".format(line_style, s.property("path"))
                          )
        io.console.print(table)
