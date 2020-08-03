import sys
import click
import logging
from pcvsrt import globals

try:
    import cowsay
except ImportError:
    pass


FORMAT = "%(levelname)s: %(message)s"
enrich_display = False
glyphs = {
    'copy': '(c)',
    'item': '*',
    'sec': '#',
    'hdr': '=',
    'star': '*',
    'fail': 'X',
    'succ': 'V',
    'git': '(git)',
    'time': '(time)',
    'full_pg': '#',
    'empty_pg': '-',
    'sep_v': " | ",
    'sep_h': "-"
}


def __set_logger(v):
    lv = None
    if v > 1:
        lv = logging.DEBUG
    elif v > 0:
        lv = logging.INFO
    else:
        lv = logging.WARNING

    logging.basicConfig(format=FORMAT, level=lv)
    logging.disabled = True


def __set_encoding(e):
    global glyphs
    if e and 'utf-' in sys.getdefaultencoding():
        glyphs['copy'] = '\u00A9'
        glyphs['item'] = '\u27E2'
        glyphs['sec'] = '\u2756'
        glyphs['hdr'] = '\u23BC'
        glyphs['star'] = '\u2605'
        glyphs['fail'] = click.style('\u2716', fg="red", bold=True)
        glyphs['succ'] = click.style('\u2714', fg="green")
        glyphs['git'] = '\u237F'
        glyphs['time'] = '\U0000231A'
        glyphs['full_pg'] = click.style("\u2588", fg="bright_black")
        glyphs['empty_pg'] = click.style("\u26AC", fg='cyan')
        glyphs['sep_v'] = " \u237F "
        glyphs['sep_h'] = "\u23BC"


def init(verbose, encoding, enrich_exp=False):
    global enrich_display
    __set_logger(verbose)
    __set_encoding(encoding)
    if enrich_exp:
        if not cowsay:
            logs.warn(
                "Unable to enrich your experience without the following modules:",
                " - cowsay"
            )
        else:
            enrich_display = True


def cl(s, color='reset', **args):
    return click.style(s, fg=color, **args)


def utf(k):
    global glyphs
    assert(k in glyphs.keys())
    return glyphs[k]


def print_header(s, out=True):
    hdr_char = utf('hdr')
    str_len = globals.LINELENGTH - (len(s) + 2)  # surrounding spaces
    begin = hdr_char * int(str_len / 2)
    end = begin + (hdr_char * (str_len % 2 != 0))

    s = click.style("{} {} {}".format(begin, s.upper(), end), fg="green")
    if out:
        click.echo(s, err=True)
    else:
        return s
    pass


def print_section(s, out=True):
    f = "{} {}".format(utf('sec'), s)
    s = click.style(f, fg='yellow', blink=True)
    if out:
        click.echo(s, err=True)
    else:
        return s


def print_item(s, depth=1, out=True):
    bullet = ("   " * depth) + "{} ".format(utf('item'))
    content = "{}".format(s)

    s = click.style(bullet, fg="red") + click.style(content, fg="reset")
    if out:
        click.echo(s, err=True)
    else:
        return s


def debug(*msg):
    for elt in msg:
        for line in elt.split('\n'):
            logging.debug(click.style(line, fg="bright_black"))


def info(*msg):
    for elt in msg:
        for line in elt.split('\n'):
            logging.info(click.style(line, fg="cyan"))


def warn(*msg):
    for elt in msg:
        for line in elt.split('\n'):
            logging.warning(click.style(line, fg="yellow", bold=True))


def err(*msg, abort=0):
    global enrich_display
    for elt in msg:
        for line in elt.split('\n'):
            logging.error(click.style(line, fg="red", bold=True))

    if abort:
        if enrich_display:
            cowsay.tux(
                "Im sorry but an unfortunate error forced me to stop this program"
                "If I'm doing it wrong, feel free to yell at people who coded"
                " me. Sorry for the inconvenience."
                )
        else:
            logging.error(click.style(
                "Fatal error(s) above. The program will now stop!",
                fg="red", bold=True))
        sys.exit(abort)


def nimpl(*msg):
    global enrich_display
    s = "'{}' not implemented yet! (WIP)".format(*msg)
    if enrich_display:
        cowsay.daemon(click.style(s, fg="yellow", bold=True))
    else:
        warn(s)


def nreach(*msg):
    if enrich_display:
        cowsay.tux(
            "Uh oh, I reached this point but one ever told me I'll never go "
            "that far! I'm afraid something really bad happened. Please send "
            "help, I'm scared! Here are my coordinates: {}".format(*msg))
    else:
        err(click.style("{} should not be reached in any way! "
            "Something went wrong".format(*msg), fg='red', bold=True))


def enrich_print(*msg, skippable=False):
    global enrich_display
    if enrich_display:
        cowsay.tux(*msg)
    elif skippable is False:
        click.secho(*msg)


def print_n_stop(**kwargs):
    for k, v in kwargs.items():
        click.secho("{}: ".format(k), fg="yellow", nl=False)
        click.secho("'{}'".format(v), fg="blue")
    sys.exit(0)


def progbar(it, **kargs):
    return click.progressbar(it, empty_char=utf('empty_pg'),
                             info_sep=utf('sep_v'), fill_char=utf('full_pg'),
                             show_percent=False, show_eta=False, show_pos=True,
                             **kargs)


def banner():
    # ok,  this is ugly but the only way to make flake/pylint happy with
    # source file formatting AND keeping a nicely logo printed out witout
    # having to load a file.
    # But, it is not trivial to edit. A single terminal line is split in
    # half. Each 'logo' value is a line, created from the implicit
    # concatenation of multiple raw strings (ex: logo= [r"a" r"b", r"c"])
    #
    # the full header can be found under the /utils/ source dir.
    logo = [
        r"""    ____                   ____     __   ______         """
        r"""                   __  _            """,
        r"""   / __ \____ __________ _/ / /__  / /  / ____/___  ____"""
        r""" ___  ____  __  __/ /_(_)___  ____ _""",
        r"""  / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ """
        r"""`__ \/ __ \/ / / / __/ / __ \/ __ `/""",
        r""" / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / """
        r"""/ / / /_/ / /_/ / /_/ / / / / /_/ / """,
        r"""/_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/"""
        r""" /_/ .___/\__,_/\__/_/_/ /_/\__, /  """,
        r"""                                                        """
        r"""  /_/                      /____/   """,
        r"""                                       {} (PCVS) {}     """
        r"""                           """.format(utf('star'), utf('star')),
        r"""          _    __      ___     __      __  _            """
        r"""    _____       _ __                """,
        r"""         | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____  """
        r"""   / ___/__  __(_) /____            """,
        r"""         | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \ """
        r"""   \__ \/ / / / / __/ _ \           """,
        r"""         | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / / """
        r"""  ___/ / /_/ / / /_/  __/           """,
        r"""         |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/  """
        r""" /____/\__,_/_/\__/\___/            """,
        r"""                                                        """
        r"""                                    """,
        r"""   Copyright {} 2017 Commissariat à l'Énergie Atomique e"""
        r"""t aux Énergies Alternatives (CEA)   """.format(utf('copy')),
        r"""                                                        """
        r"""                                    """,
        r"""  This program comes with ABSOLUTELY NO WARRANTY;       """
        r"""                                    """,
        r"""  This is free software, and you are welcome to redistri"""
        r"""bute it                             """,
        r"""  under certain conditions; Please see COPYING for detai"""
        r"""ls.                                 """,
        r"""                                                        """
        r"""                                    """,
    ]

    click.secho("\n".join(logo[0:6]), fg="green")
    click.secho("\n".join(logo[6:7]))
    click.secho("\n".join(logo[7:9]), fg="green")
    click.secho("\n".join(logo[9:11]), fg="yellow")
    click.secho("\n".join(logo[11:12]), fg="red")
    click.secho("\n".join(logo[12:]))
