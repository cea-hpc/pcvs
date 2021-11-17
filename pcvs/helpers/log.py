import functools
import os
import pprint
import sys
import textwrap
import traceback

import click

from pcvs.helpers import exceptions
from pcvs.helpers.exceptions import CommonException


def pretty_print_exception(e: exceptions.GenericError):
    """Display exceptions in a fancy way.

    :param e: the execption to print
    :type e: exceptions.GenericError.
    """
    global manager
    if isinstance(e, exceptions.GenericError):
        manager.err([e.err, e.help])
        manager.info("Extra infos:\n{}".format(e.dbg_str))
    else:
        manager.err(str(e))


class IOManager:
    """
    Manager for Input/Output streams.

    Contains methods for logging and printing in PCVS. IOManager handles
    multiple outputs (file + standard output), logging levels (warning, error,
    info, etc) and pretty banners. Colors are handled by click and color tags
    are written in files (use less -r).

    :param special_chars: dictionary for fancy bullet characters
    :type special_chars: dict
    :param verb_levels: verbosity level (normal, info, debug)
    :type verb_levels: list
    :param color_list: list of colors used by PCVS
    :type color_list: list
    """
    special_chars = {
        "ascii": {
            'copy': '(c)',
            'item': '*',
            'sec': '#',
            'hdr': '=',
            'star': '*',
            'fail': "X",
            'succ': "V",
            'none': "-",
            'git': '(git)',
            'time': '(time)',
            'full_pg': '#',
            'empty_pg': '-',
            'sep_v': " | ",
            'sep_h': "-"
        },
        "unicode": {
            'copy': '\u00A9',
            'item': '\u27E2',
            'sec': '\u2756',
            'hdr': '\u23BC',
            'star': '\u2605',
            'fail': '\u2718',
            'succ': '\u2714',
            "none": '\u2205',
            'git': '\u237F',
            'time': '\U0000231A',
            'full_pg': click.style("\u25CF", bold=True, fg="cyan"),
            'empty_pg': click.style("\u25CB", bold=True, fg="bright_black"),
            'sep_v': " \u237F ",
            'sep_h': "\u23BC"
        }
    }

    verb_levels = [(0, "normal"), (1, "info"), (2, "debug")]

    color_list = [
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

    @property
    def verbose(self):
        """getter for verbosity level

        :return: verbosity level (0, 1, 2)
        :rtype: int
        """
        return self._verbose

    @property
    def tty(self):
        """getter for tty information

        :return: False if tty not used, 1 if tty used
        :rtype: bool
        """
        return self._tty

    def set_tty(self, enable):
        """[summary]

        :param enable: [description]
        :type enable: [type]
        """
        self._tty = enable

    def enable_tty(self):
        """enables tty
        """
        self.set_tty(enable=True)

    def disable_tty(self):
        """disables tty
        """
        self.set_tty(enable=False)

    @property
    def log_filename(self):
        """getter for logfile path

        :return: logfile path
        :rtype: str
        """
        return os.path.abspath(self._logfile.name) if self._logfile else None

    def set_logfile(self, enable, logfile=None):
        """setter for logfile path

        :param logfile: logfile name, defaults to None
        :type logfile: str, optional
        """

        if logfile is not None:
            if not os.access(os.path.dirname(logfile), os.W_OK):
                raise CommonException.IOError(
                    "{} is not writable !".format(logfile))

            if os.path.abspath(logfile) != self.log_filename:
                self._logfile = open(os.path.abspath(logfile), 'w+')
            self._logenabled = enable

    def __init__(self, verbose=0, enable_unicode=True, length=80, logfile=None, tty=True):
        """constructor for IOManager object

        :param verbose: verbosity level (0 : low, 1: info, 2: debug), defaults
            to 0
        :type verbose: int, optional
        :param enable_unicode: True if unicode alphabet usage is authorised,
            defaults to True
        :type enable_unicode: bool, optional
        :param length: length of terminal (character number), defaults to 80
        :type length: int, optional
        :param logfile: logfile name, file logging disabled if logfile=None,
            defaults to None
        :type logfile: str, optional
        :param tty: True if logs must be in stdout, defaults to True
        :type tty: bool, optional
        :raises CommonException.AlreadyExistError: only one IOManager can
            exist in a session
        """
        self._linelength = 93
        self._wrapper = None
        self._tty = tty
        self._logfile = None
        self._verbose = verbose
        self._unicode = enable_unicode
        self._logbuffer = ""
        self._logenabled = False

        self.enable_unicode(self._unicode)

        if length is not None:
            self._linelength = length if length > 0 else click.get_terminal_size()[
                0]
        self._wrapper = textwrap.TextWrapper(width=self._linelength)

        if logfile is not None:
            logfile = os.path.abspath(logfile)
            if os.path.isfile(logfile):
                raise CommonException.AlreadyExistError(logfile)

            self.set_logfile(True, logfile)

    def __del__(self):
        """desctuctor for IOManager (closes streams)
        """

        if self._logfile:
            if not os.path.isfile(self._logfile.name):
                manager.warn("{} does not exist anymore !".format(
                    self._logfile.name))
            else:
                self._logfile.close()

    def __print_rawline(self, msg, err=False):
        """print a line as text

        :param msg: message to be printed
        :type msg: str
        :param err: True if the message is an error message, defaults to False
        :type err: bool, optional
        """
        if self._tty:
            click.echo(msg, err=err)

        content = '{}{}'.format(msg, '\n' if msg[-1] != "\n" else "")
        if self._logenabled and self._logfile:
            self._logfile.write(self._logbuffer)
            self._logfile.write(content)
            self._logfile.flush()
            self._logbuffer = ""
        else:
            self._logbuffer += content

    def has_verb_level(self, match):
        """ returns true if the verbosity level is activated.

        :param match: verbosity level to check
        :type match: str or int
        :return: True if "match" verbosity level is supposed to be printed by
            the IOManager
        :rtype: bool
        """
        req_idx = 0
        for e in self.verb_levels:
            if match.lower() == e[1].lower():
                req_idx = e[0]
                break
        return req_idx <= self._verbose

    def get_verbosity_str(self):
        """[summary]

        :return: [description]
        :rtype: [type]
        """
        for e in self.verb_levels:
            if self._verbose == e[0]:
                return e[1]
        return self.verb_levels[0][1]

    def print(self, *msg):
        """prints a raw line. Takes multiple arguments.
        """
        for i in msg:
            self.__print_rawline(i)

    def write(self, txt):
        """print a string.

        :param txt: message to be printed
        :type txt: str
        """
        self.__print_rawline(txt)

    def capture_exception(self, e_type, user_func=None):
        """wraps functions to capture unhandled exceptions for high-level
            function not to crash.
            :param *e_type: errors to be caught
        """
        def inner_function(func):
            """wrapper for inner function using try/except to avoid crashing

            :param func: function to wrap
            :type func: function
            :raises e: exceptions to catch
            :return: wrapper
            :rtype: function
            """
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                """functools wrapping function

                :raises e: exception to catch
                :return: result of wrapped function
                :rtype: any
                """
                try:
                    return func(*args, **kwargs)
                except e_type as e:
                    #raise e
                    if user_func is None:
                        pretty_print_exception(e)
                        manager.debug(
                            traceback.format_exception(*sys.exc_info()))
                        sys.exit(1)
                    else:
                        user_func(e)
            return wrapper
        return inner_function

    def enable_unicode(self, e=True):
        """enables/disables unicode alphabet usage

        :param e: True to enable unicode usage, defaults to True
        :type e: bool, optional
        """
        self.glyphs = self.special_chars["unicode"] if e is True else self.special_chars["ascii"]

    def avail_chars(self):
        """lists allowed bullet characters

        :return: a list of characters
        :rtype: list
        """
        return self.glyphs.keys()

    def utf(self, k):
        """returns the corresponding character to a bullet character

        :param k: character used as bullet character
        :type k: char
        :return: fancy bullet character
        :rtype: char
        """
        assert(k in self.glyphs.keys())
        return self.glyphs[k]

    def style(self, *args, **kwargs):
        """returns a string style using click

        :return: a string style
        :rtype: click.style
        """
        return click.style(*args, **kwargs)

    def print_header(self, s, out=True):
        """prints a header

        :param s: header content
        :type s: str
        :param out: True if the header has to be logged, False if it has to be
            returned, defaults to True
        :type out: bool, optional
        :return: header string if out=False, Nothing otherwise
        :rtype: str
        """
        hdr_char = self.utf('hdr')
        str_len = self._linelength - (len(s) + 2)  # surrounding spaces
        # nb chars before the title (centering)
        begin = hdr_char * int(str_len / 2)
        # nb chars after the title (centering)
        end = begin + (hdr_char * (str_len % 2 != 0))

        # formatting & colouring
        final_string = click.style("\n{} {} {}".format(
            begin, s.upper(), end), fg="green")
        if out:
            self.__print_rawline(final_string)
        else:
            return final_string

    def print_section(self, s, out=True):
        """prints a section

        :param s: content of the section
        :type s: str
        :param out: True if the section has to be logged, False if it has to be
            returned, defaults to True
        :type out: bool, optional
        :return: section string if out=False, Nothing otherwise
        :rtype: str
        """
        f = "{} {}".format(self.utf('sec'), s)
        self._wrapper.subsequent_indent = "  "
        s = self._wrapper.fill(click.style(f, fg='yellow'))
        if out:
            self.__print_rawline(s)
        else:
            return s

    def print_item(self, s, depth=1, out=True, with_bullet=True):
        """prints an item

        :param s: item content
        :type s: str
        :param depth: number of tabulations used for indentation, defaults to 1
        :type depth: int, optional
        :param out: True if the item has to be logged, False if it has to be
            returned, defaults to True
        :type out: bool, optional
        :param with_bullet: True if the item should have a bullet, defaults to True
        :type with_bullet: bool, optional
        :return: item string if out=False, Nothing otherwise
        :rtype: str
        """
        indent = ("   " * depth)
        bullet = indent + \
            "{} ".format(self.utf('item')) if with_bullet is True else ""
        content = "{}".format(s)

        self._wrapper.subsequent_indent = indent + "  "
        s = self._wrapper.fill(click.style(
            bullet, fg="red") + click.style(content, fg="reset"))
        if out:
            self.__print_rawline(s)
        else:
            return s

    def print_job(self, label, time, name, colorname="red", icon=None):
        """prints a job description

        :param label: job label
        :type label: str
        :param time: time elapsed since the job launch
        :type time: float
        :param name: name of the job
        :type name: str
        :param colorname: color of the job log, defaults to "red"
        :type colorname: str, optional
        :param icon: bullet, defaults to None
        :type icon: str, optional
        """
        if icon is not None:
            icon = self.utf(icon)
        self.__print_rawline(click.style("   {} {:8.2f}s{}{:7}{}{}".format(
            icon,
            time,
            self.utf("sep_v"),
            label,
            self.utf("sep_v"),
            name),
            fg=colorname, bold=True))

    def debug(self, msg):
        """prints a debug message
        """
        if(self._verbose >= 2):
            if type(msg) != list:
                msg = [msg]
            for elt in msg:
                for line in elt.split('\n'):
                    self.__print_rawline("DEBUG: {}".format(
                        click.style(line, fg="bright_black")), err=True)

    def info(self, msg):
        """prints an info message
        """
        if(self._verbose >= 1):
            if type(msg) != list:
                msg = [msg]
            for elt in msg:
                for line in elt.split('\n'):
                    self.__print_rawline("INFO : {}".format(
                        click.style(line, fg="cyan")),  err=True)

    def warn(self, msg):
        """prints a warning message
        """
        if type(msg) != list:
            msg = [msg]
        for elt in msg:
            for line in elt.split('\n'):
                self.__print_rawline("WARN : {}".format(
                    click.style(line, fg="yellow", bold=True)),  err=True)

    def err(self, msg):
        """prints an error message
        """
        if type(msg) != list:
            msg = [msg]
        enclosing_line = click.style(self.utf('hdr') * self._linelength,
                                     fg="red",
                                     bold=True)
        self.__print_rawline("{}".format(enclosing_line),  err=True)
        for elt in msg:
            for line in elt.split('\n'):
                self.__print_rawline("ERROR: {}".format(
                    click.style(line, fg="red", bold=True)),  err=True)
        self.__print_rawline("{}".format(enclosing_line),  err=True)

    def print_short_banner(self, string=False):
        """prints a little banner

        :param string: True if the banner has to be returned, False if it has to be logged
        :type string: bool
        """
        logo = [
            r"""             ____    ______  _    __  _____       """,
            r"""            / __ \  / ____/ | |  / / / ___/       """,
            r"""           / /_/ / / /      | | / /  \__ \        """,
            r"""          / ____/ / /___    | |/ /  ___/ /        """,
            r"""         /_/      \____/    |___/  /____/         """,
            r"""                                                  """,
            r"""      Parallel Computing -- Validation System     """,
            r"""             Copyright {} 2017 -- CEA             """.format(
                self.utf('copy')),
            r""""""
        ]
        s = []
        if self._linelength < max(map(lambda x: len(x), logo)):
            s = [
                click.style("{}".format(self.utf("star")*14), fg="green"),
                click.style("{} -- PCVS -- {}".format(self.utf("star"),
                            self.utf('star')), fg="yellow"),
                click.style("{} CEA {} 2017 {}".format(
                    self.utf('star'), self.utf('copy'), self.utf('star')), fg="red"),
                click.style("{}".format(self.utf("star")*14), fg="green")
            ]
        else:
            start = " " * ((self._linelength - len(logo[0]))//2-1)
            newline = "\n" + start
            s = [
                click.style(start + newline.join(logo[0:3]), fg="green"),
                click.style(start + newline.join(logo[3:4]), fg="yellow"),
                click.style(start + newline.join(logo[4:5]), fg="red"),
                click.style(start + newline.join(logo[5:]))
            ]
        if string is True:
            return "\n".join(s)
        else:
            self.__print_rawline("\n".join(s))

    def nimpl(self, *msg):  # pragma: no cover
        """prints the "not implemented" error
        """
        self.err("This is not implemented (yet)!")

    def print_n_stop(self, **kwargs):  # pragma: no cover
        """prints a message, then exits the program
        """
        # not replacing these prints (for debug only)
        for k, v in kwargs.items():
            click.secho("{}: ".format(k), fg="yellow", nl=False)
            click.secho(pprint.pformat(v), fg="blue")
        sys.exit(0)

    def print_banner(self):
        """prints a large banner
        """
        # ok,  this is ugly but the only way to make flake/pylint happy with
        # source file formatting AND keeping a nicely logo printed out witout
        # having to load a file.
        # But, it is not trivial to edit. A single terminal line is split in
        # half. Each 'logo' value is a line, created from the implicit
        # concatenation of multiple raw strings (ex: logo= [r"a" r"b", r"c"])
        #
        # the full header can be found under the /utils/ source dir.
        logo = [
            r"""    ____                   ____     __   ______                            __  _             """,
            r"""   / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _ """,
            r"""  / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/ """,
            r""" / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ /  """,
            r"""/_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /   """,
            r"""                                                          /_/                     /____/     """,
            r"""                                              {} (PCVS) {}""".format(
                self.utf('star'), self.utf('star')),
            r"""    _    __      ___     __      __  _                _____            __                    """,
            r"""   | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  _______/ /____  ____ ___      """,
            r"""   | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / ___/ __/ _ \/ __ `__ \     """,
            r"""   | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ /__  / /_/  __/ / / / / /     """,
            r"""   |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__, /____/\__/\___/_/ /_/ /_/      """,
            r"""                                                        /____/                               """,
            r"""                                                                                            """,
            r"""   Copyright {} 2017 Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)   """.format(
                self.utf('copy')),
            r"""                                                                                            """,
            r"""  This program comes with ABSOLUTELY NO WARRANTY;                                           """,
            r"""  This is free software, and you are welcome to redistribute it                             """,
            r"""  under certain conditions; Please see COPYING for details.                                 """,
            r"""                                                                                            """,
        ]

        if self._linelength < max(map(lambda x: len(x), logo)):

            self.print_short_banner()
            return
        else:
            start = " " * ((self._linelength - len(logo[0]))//2-1)
            newline = "\n" + start
            self.__print_rawline(click.style(
                start + newline.join(logo[0:6]), fg="green"))
            self.__print_rawline(click.style(start + newline.join(logo[6:7])))
            self.__print_rawline(click.style(start +
                                             newline.join(logo[7:10]), fg="green"))
            self.__print_rawline(click.style(start +
                                             newline.join(logo[10:11]), fg="yellow"))
            self.__print_rawline(click.style(
                start + newline.join(logo[11:13]), fg="red"))
            self.__print_rawline(click.style(start + newline.join(logo[13:])))


manager = IOManager()


def init(v=0, e=False, l=100, quiet=False):
    """initializes a global manager for everyone to use

    :param v: verbosity level, defaults to 0
    :type v: int, optional
    :param e: True to enable unicode alphabet, False to use ascii, defaults to
        False
    :type e: bool, optional
    :param l: length of the terminal, defaults to 100
    :type l: int, optional
    :param quiet: False to write to stdout, defaults to False
    :type quiet: bool, optional
    """
    global manager
    manager = IOManager(verbose=v, enable_unicode=e, length=l, tty=(not quiet))


def progbar(it, print_func=None, man=None, **kargs):
    """prints a progress bar using click

    :param it: iterable on which the progress bar has to iterate
    :type it: iterable
    :param print_func: method used to show the item next to the progress bar,
        defaults to None
    :type print_func: function, optional
    :param man: manager used to describe the bullets, defaults to None
    :type man: log.IOManager, optional
    :return: a click progress bar (iterable)
    :rtype: click.ProgressBar
    """
    if man is None:
        man = manager
    return click.progressbar(
        it, empty_char=man.utf('empty_pg'),
        info_sep=man.utf('sep_v'), fill_char=man.utf('full_pg'),
        show_percent=False, show_eta=False, show_pos=False,
        item_show_func=print_func,
        **kargs)
