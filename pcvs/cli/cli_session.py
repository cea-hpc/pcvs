from logging import Filter
import click
import re

from pcvs.backend import session as pvSession
from pcvs.helpers import log


def compl_session_token(ctx, args, incomplete) -> list:
    sessions = run.list_alive_sessions()
    return [(k, v) for k, v in sessions.items() if incomplete in k]


@click.group(name="session", short_help="Manage multiple validations")
@click.pass_context
def session(ctx):
    pass

@session.command(name="list", short_help="list alive sessions")
@click.option("-r", "--regex", "regex", type=str, default=None,
              help="Restrict the view to specific sessions")
@click.option('-v', '--verbose', 'verbose', default=False, is_flag=True,
              help="Detailed view for each session")
@click.pass_context
def session_list(ctx, regex, verbose):
    log.print_header("Session View")
    sessions = pvSession.list_alive_sessions()
    
    if not sessions:
        log.print_item("None")
        return
    for sk, sv in sessions.items():
        if regex and not re.match(regex, sk):
            continue
        if verbose:
            log.print_item("{}: need verbose mode".format(sk))
        else:
            log.print_item("ID {: >2s}: {}".format(str(sk),
                                            log.cl(pvSession.Session.str_state(sv['state']), 'bright_black')))


@session.command(name="attach", short_help="attach the shell to alive session")
@click.argument("name", autocompletion=compl_session_token)
@click.pass_context
def session_attach(ctx, name):
    log.warn("WIP")

@session.command(name="ctl", short_help="Alter in-progress validation")
@click.argument("name", autocompletion=compl_session_token)
@click.option("-p", "--pause", "pause", is_flag=True, default=False,
              help="Pause the given session")
@click.option("-r", "--resume", "resume", is_flag=True, default=False,
              help="Resume the given session")
@click.pass_context
def session_control(ctx, name, pause, resume):
    log.warn("WIP")