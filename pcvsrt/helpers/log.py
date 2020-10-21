import sys
import click
import logging
import pprint
import textwrap
import sys
import locale
import os
import subprocess


linelength = 93
FORMAT = "%(levelname)s: %(message)s"
wrapper = None
vb_array = {
    'normal': (0, logging.WARNING),
    'info': (1, logging.INFO),
    'debug': (2, logging.DEBUG)
}
verbosity = 0
glyphs = {
    'copy': '(c)',
    'item': '*',
    'sec': '#',
    'hdr': '=',
    'star': '*',
    'fail': click.style('X', fg='red', bold=True),
    'succ': click.style('V', fg='green'),
    'git': '(git)',
    'time': '(time)',
    'full_pg': '#',
    'empty_pg': '-',
    'sep_v': " | ",
    'sep_h': "-"
}

all_colors = [
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_black",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
]


def __set_logger(v):
    global vb_array
    global verbosity
    verbosity = max(min(v, len(vb_array)-1), 0)
    for _, v in vb_array.items():
        if verbosity == v[0]:
            logging.basicConfig(format=FORMAT, level=v[1])


def get_verbosity(match):
    global vb_array
    assert(match in vb_array.keys())
    return vb_array[match][0] <= verbosity


def get_verbosity_str():
    for k, v in vb_array.items():
        if v[0] == verbosity:
            return k


def init_tee(path):
    t = subprocess.Popen(["tee", os.path.join(path, 'out.log')],
                         stdin=subprocess.PIPE)
    os.dup2(t.stdin.fileno(), sys.stdout.fileno())
    os.dup2(t.stdin.fileno(), sys.stderr.fileno())


def __set_encoding(e):
    global glyphs
    if e and 'utf-' in locale.getpreferredencoding().lower():
        glyphs['copy'] = '\u00A9'
        glyphs['item'] = '\u27E2'
        glyphs['sec'] = '\u2756'
        glyphs['hdr'] = '\u23BC'
        glyphs['star'] = '\u2605'
        glyphs['fail'] = click.style('\u2716', fg="red", bold=True)
        glyphs['succ'] = click.style('\u2714', fg="green")
        glyphs['git'] = '\u237F'
        glyphs['time'] = '\U0000231A'
        glyphs['full_pg'] = click.style("\u2022", bold=True, fg="cyan")
        glyphs['empty_pg'] = click.style("\u25E6", bold=True, fg="bright_black")
        glyphs['sep_v'] = " \u237F "
        glyphs['sep_h'] = "\u23BC"
    else:
        glyphs = {
            'copy': '(c)',
            'item': '*',
            'sec': '#',
            'hdr': '=',
            'star': '*',
            'fail': click.style('X', fg='red', bold=True),
            'succ': click.style('V', fg='green'),
            'git': '(git)',
            'time': '(time)',
            'full_pg': '#',
            'empty_pg': '-',
            'sep_v': " | ",
            'sep_h': "-"
    }


def init(verbose, encoding, length):
    global wrapper, linelength
    __set_logger(verbose)
    __set_encoding(encoding)

    if length is not None:
        linelength = length if length > 0 else click.get_terminal_size()[0]
    wrapper = textwrap.TextWrapper(width=linelength)


def cl(s, color='reset', **args):
    return click.style(s, fg=color, **args)


def utf(k):
    global glyphs
    assert(k in glyphs.keys())
    return glyphs[k]


def print_header(s, out=True):
    global wrapper, linelength
    hdr_char = utf('hdr')
    str_len = linelength - (len(s) + 2 + 9)  # surrounding spaces  + color ID
    begin = hdr_char * int(str_len / 2)
    end = begin + (hdr_char * (str_len % 2 != 0))

    fs = click.style("{} {} {}".format(begin, s.upper(), end), fg="green")
    if len(fs) > linelength:
        fs = click.style("{} {} {}".format(2*hdr_char, s.upper(), 2*hdr_char), fg="green")
    
    wrapper.subsequent_indent = (2*hdr_char) + " "
    fs = wrapper.fill(fs)
    if out:
        click.echo(fs, err=True)
    else:
        return fs
    pass


def print_section(s, out=True):
    global wrapper
    f = "{} {}".format(utf('sec'), s)
    wrapper.subsequent_indent = "  "
    s = wrapper.fill(click.style(f, fg='yellow'))
    if out:
        click.echo(s, err=True)
    else:
        return s


def print_item(s, depth=1, out=True, with_bullet=True):
    global wrapper
    indent = ("   " * depth)
    bullet = indent + "{} ".format(utf('item')) if with_bullet is True else ""
    content = "{}".format(s)

    wrapper.subsequent_indent = indent + "  "
    s = wrapper.fill(click.style(bullet, fg="red") + click.style(content, fg="reset"))
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


def err(*msg, abort=1):
    for elt in msg:
        for line in elt.split('\n'):
            logging.error(click.style(line, fg="red", bold=True))

    if abort:
        logging.error(click.style(
                "Fatal error(s) above. The program will now stop!",
                fg="red", bold=True))
        sys.exit(abort)


def nimpl(*msg):
    cowsay.daemon(click.style("'{}' not implemented yet! (WIP)".format(*msg),
                  fg="yellow", bold=True))
    err("")


def nreach(*msg):
    cowsay.tux("""
    Uh oh, I reached this point but one ever told me I'll never go 
    that far! I'm afraid something really bad happened. Please send 
    help, I'm scared! Here are my coordinates: {}
    """.format(*msg))
    

def print_n_stop(**kwargs):
    for k, v in kwargs.items():
        click.secho("{}: ".format(k), fg="yellow", nl=False)
        click.secho(pprint.pformat(v), fg="blue")
    sys.exit(0)


def progbar(it, print_func=None, **kargs):
    return click.progressbar(it, empty_char=utf('empty_pg'),
                             info_sep=utf('sep_v'), fill_char=utf('full_pg'),
                             show_percent=False, show_eta=False, show_pos=False,
                             item_show_func=print_func,
                             **kargs)


def short_banner(string=False):
    logo =[
        r"""             ____    ______  _    __  _____       """,
        r"""            / __ \  / ____/ | |  / / / ___/       """,
        r"""           / /_/ / / /      | | / /  \__ \        """,
        r"""          / ____/ / /___    | |/ /  ___/ /        """,
        r"""         /_/      \____/    |___/  /____/         """,
        r"""                                                  """,
        r"""      Parallel Computing -- Validation Suite      """,
        r"""             Copyright {} 2017 -- CEA             """.format(utf('copy')),
        r""""""
    ]
    s = []
    if linelength < max(map(lambda x: len(x), logo)):
        s = [
            click.style("{}".format(utf("star")*14), fg="green"),
            click.style("{} PCVS -- RT {}".format(utf("star"), utf('star')), fg="yellow"),
            click.style("{} CEA {} 2017 {}".format(utf('star'), utf('copy'), utf('star')), fg="red"),
            click.style("{}".format(utf("star")*14), fg="green")
        ]
    else:
        s = [
            click.style("\n".join(logo[0:3]), fg="green"),
            click.style("\n".join(logo[3:4]), fg="yellow"),
            click.style("\n".join(logo[4:5]), fg="red"),
            click.style("\n".join(logo[5:]))
        ]
    if string is True:
        return "\n".join(s)
    else:
        click.echo("\n".join(s))


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
    if linelength < max(map(lambda x: len(x), logo)):
        short_banner()
        return
    else:
        click.secho("\n".join(logo[0:6]), fg="green")
        click.secho("\n".join(logo[6:7]))
        click.secho("\n".join(logo[7:9]), fg="green")
        click.secho("\n".join(logo[9:11]), fg="yellow")
        click.secho("\n".join(logo[11:12]), fg="red")
        click.secho("\n".join(logo[12:]))
