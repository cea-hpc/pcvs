from datetime import datetime

import click

from pcvs.backend import session as pvSession
from pcvs.helpers import log


def compl_session_token(ctx, args, incomplete) -> list:
    sessions = pvSession.list_alive_sessions()
    if sessions is None:
        return []
    return [(k, pvSession.Session.str_state(v['state'])) for k, v in sessions.items() if incomplete in str(k)]


@click.command(name="session", short_help="Manage multiple validations")
@click.option('-c', '--ack', 'ack', type=int, default=None,
              help="acknowledge a 'completed' session, for removing from logs")
@click.option('-C', '--ack-all', 'ack_all', is_flag=True, default=False,
              help="Ack all completed sessions, for removing from logs")
@click.option('-l', '--list', is_flag=True,
              help="List detached sessions")
@click.pass_context
def session(ctx, ack, list, ack_all):
    sessions = pvSession.list_alive_sessions()
    if sessions is None:
        sessions = dict()

    if ack_all is True:
        for session_id in sessions.keys():
            if sessions[session_id]['state'] != pvSession.Session.STATE_IN_PROGRESS:
                pvSession.remove_session_from_file(session_id)
    elif ack is not None:
        pvSession.remove_session_from_file(ack)
    else:  # listing is the defualt
        log.manager.print_header("Session View")
        for sk, sv in sessions.items():
            s = pvSession.Session()
            s.load_from(sk, sv)

            if s.state == pvSession.Session.STATE_IN_PROGRESS:
                extra_line = "In Progress (for {})".format(
                    str(datetime.now() - s.property('started'))
                )
            elif s.state == pvSession.Session.STATE_COMPLETED:
                extra_line = "Completed (lasted {})".format(
                    str(s.property('ended') - s.property('started'))
                )
            else:
                extra_line = "Error"

            log.manager.print_item("ID {: >2s}: {}".format(str(s.id), extra_line))
