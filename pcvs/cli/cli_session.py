import os
from datetime import datetime, timedelta

import click

from pcvs import NAME_BUILDFILE
from pcvs.backend import session as pvSession
from pcvs.helpers import log, utils


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
    return [(k, str(pvSession.Session.State(v['state']))) for k, v in sessions.items() if incomplete in str(k)]


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
        log.manager.print_header("Session View")
        for sk, sv in sessions.items():
            s = pvSession.Session()
            s.load_from(sk, sv)
            status = "Broken"
            duration = timedelta()

            if s.state == pvSession.Session.State.IN_PROGRESS:
                duration = datetime.now() - s.property('started')
                status = "In Progress -- {:4.2f}%".format(
                    s.property('progress'))
            elif s.state == pvSession.Session.State.COMPLETED:
                duration = s.property('ended') - s.property('started')
                status = "Completed"
            elif s.state == pvSession.Session.State.WAITING:
                duration = datetime.now() - s.property('started')
                status = "Waiting"

            log.manager.print_item("SID #{:0>6s}: {} ({})".format(
                str(s.id),
                status.upper(),
                str(timedelta(days=duration.days, seconds=duration.seconds))
            ))
