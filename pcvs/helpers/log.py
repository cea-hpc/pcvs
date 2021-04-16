import functools
import os
import pprint
import sys
import textwrap

import click

from pcvs.helpers.exceptions import CommonException


manager = None
def init(v=0, e=False, l=100):
    global manager
    manager = IOManager(verbose=v, enable_unicode=e, length=l)

def progbar(it, print_func=None, man=None, **kargs):
    if(man == None):
        man = manager
    return click.progressbar(
            it,empty_char=man.utf('empty_pg'),
            info_sep=man.utf('sep_v'), fill_char=man.utf('full_pg'),
            show_percent=False, show_eta=False, show_pos=False,
            item_show_func=print_func,
            **kargs)

class IOManager:
    special_chars = {
        "ascii": {
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
        },
        "unicode": {
            'copy' : '\u00A9',
            'item' : '\u27E2',
            'sec' : '\u2756',
            'hdr' : '\u23BC',
            'star' : '\u2605',
            'fail' : click.style('\u2716', fg="red", bold=True),
            'succ' : click.style('\u2714', fg="green"),
            'git' : '\u237F',
            'time' : '\U0000231A',
            'full_pg' : click.style("\u25CF", bold=True, fg="cyan"),
            'empty_pg' : click.style("\u25CB", bold=True, fg="bright_black"),
            'sep_v' : " \u237F ",
            'sep_h' : "\u23BC"
        }
    }

    verb_levels = [(0, "normal"), (1, "info"), (2, "debug")]
    
    __color_list = [
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
        return self._verbose
    
    @property
    def tty(self):
        return self._tty

    def set_tty(self, enable):
        self._tty = enable

    def enable_tty(self):
        self.set_tty(enable=True)

    def disable_tty(self):
        self.set_tty(enable=False)
    
    @property
    def log_filename(self):
        return os.path.abspath(self._logfile.name) if self._logfile else None

    def set_logfile(self, enable, logfile=None):
        self._logs = enable
        if logfile is not None and os.path.abspath(logfile) != self.log_filename:
            self._logfile = open(os.path.abspath(logfile), 'w+')
    
    def enable_logfile(self):
        self.set_logfile(enable=True)

    def disable_logfile(self):
        self.set_logfile(enable=False)

    def __init__(self, verbose=0, enable_unicode=True, length=80, logfile=None, tty=True):
        self._linelength = 93
        self._wrapper = None
        self._tty = tty
        self._logfile = None
        self._logs = False
        self._verbose = verbose
        self._unicode = enable_unicode
        
        self.enable_unicode(self._unicode)

        if length is not None:
            self._linelength = length if length > 0 else click.get_terminal_size()[0]
        self._wrapper = textwrap.TextWrapper(width=self._linelength)
    
        if logfile is not None:
            if os.path.isfile(logfile):
                raise CommonException.AlreadyExistError(logfile)
            self._logs = True
            self._logfile = open(os.path.abspath(logfile), "w")
        
    def __del__(self):
        
        if self._logs:
            self._logfile.close()

    def __print_rawline(self, msg, err=False):
        if self._tty:
            click.echo(msg, err=err)
        if self._logs:
            self._logfile.write(msg + ('\n' if msg[-1] != "\n" else ""))
            self._logfile.flush()

    def has_verb_level(self, match):
        req_idx = 0
        for e in self.verb_levels:
            if match.lower() == e[1].lower():
                req_idx = e[0]
                break
        return req_idx <= self._verbose

    def get_verbosity_str(self):
        for e in self.verb_levels:
            if self._verbose == e[0]:
                return e[1]
        return  self.verb_levels[0][1]

    def print(self, *msg):
        for i in msg:
            self.__print_rawline(i)

    def write(self, txt):
        self.__print_rawline(txt)

    def capture_exception(self, *e_type):
        def inner_function(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except e_type as e:
                    self.print("EXCEPTION: {}".format(e))
                        
            return wrapper
        return inner_function

    def enable_unicode(self, e=True):
        self.glyphs = self.special_chars["unicode"] if e is True else self.special_chars["ascii"]
        
    def utf(self, k):
        assert(k in self.glyphs.keys())
        return self.glyphs[k]

    def style(self, *args, **kwargs):
        return click.style(*args, **kwargs)

    def print_header(self, s, out=True):
        hdr_char = self.utf('hdr')
        str_len = self._linelength - (len(s) + 2)  # surrounding spaces
        begin = hdr_char * int(str_len / 2) # nb chars before the title (centering)
        end = begin + (hdr_char * (str_len % 2 != 0)) #nb chars after the title (centering)
        
        # formatting & colouring
        final_string = click.style("{} {} {}".format(begin, s.upper(), end), fg="green")
        if out:
            self.__print_rawline(final_string)
        else:
            return final_string

    def print_section(self, s, out=True):
        f = "{} {}".format(self.utf('sec'), s)
        self._wrapper.subsequent_indent = "  " 
        s = self._wrapper.fill(click.style(f, fg='yellow'))
        if out:
            self.__print_rawline(s)
        else:
            return s

    def print_item(self, s, depth=1, out=True, with_bullet=True):
        indent = ("   " * depth)
        bullet = indent + "{} ".format(self.utf('item')) if with_bullet is True else ""
        content = "{}".format(s)

        self._wrapper.subsequent_indent = indent + "  "
        s = self._wrapper.fill(click.style(bullet, fg="red") + click.style(content, fg="reset"))
        if out:
            self.__print_rawline(s)
        else:
            return s

    def debug(self, *msg):
        if(self._verbose >= 2):
            for elt in msg:
                for line in elt.split('\n'):
                    self.__print_rawline("DEBUG: {}".format(click.style(line, fg="bright_black")), err=True)

    def info(self, *msg):
        if(self._verbose >= 1):
            for elt in msg:
                for line in elt.split('\n'):
                    self.__print_rawline("INFO: {}".format(click.style(line, fg="cyan")),  err=True)

    def warn(self, *msg):
        for elt in msg:
            for line in elt.split('\n'):
                self.__print_rawline("WARNING: {}".format(click.style(line, fg="yellow", bold=True)),  err=True)

    def err(self, *msg, abort=1):
        enclosing_line = click.style(self.utf('hdr') * self._linelength,
                                     fg="red",
                                     bold=True)
        self.__print_rawline("{}".format(enclosing_line),  err=True)
        for elt in msg:
            for line in elt.split('\n'):
                self.__print_rawline("ERROR: {}".format(click.style(line, fg="red", bold=True)),  err=True)
        self.__print_rawline("{}".format(enclosing_line),  err=True)

    def print_short_banner(self, string=False):
        logo =[
            r"""             ____    ______  _    __  _____       """,
            r"""            / __ \  / ____/ | |  / / / ___/       """,
            r"""           / /_/ / / /      | | / /  \__ \        """,
            r"""          / ____/ / /___    | |/ /  ___/ /        """,
            r"""         /_/      \____/    |___/  /____/         """,
            r"""                                                  """,
            r"""      Parallel Computing -- Validation System     """,
            r"""             Copyright {} 2017 -- CEA             """.format(self.utf('copy')),
            r""""""
        ]
        s = []
        if self._linelength < max(map(lambda x: len(x), logo)):
            s = [
                click.style("{}".format(self.utf("star")*14), fg="green"),
                click.style("{} -- PCVS -- {}".format(self.utf("star"), self.utf('star')), fg="yellow"),
                click.style("{} CEA {} 2017 {}".format(self.utf('star'), self.utf('copy'), self.utf('star')), fg="red"),
                click.style("{}".format(self.utf("star")*14), fg="green")
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
            self.__print_rawline("\n".join(s))


    def nimpl(self, *msg):  # pragma: no cover
        self.err("This is not implemented (yet)!")  

    def print_n_stop(self, **kwargs):  #pragma: no cover
        # not replacing these prints (for debug only)
        for k, v in kwargs.items():
            click.secho("{}: ".format(k), fg="yellow", nl=False)
            click.secho(pprint.pformat(v), fg="blue")
        sys.exit(0)


    def print_banner(self):
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
r"""                                              {} (PCVS) {}""".format(self.utf('star'), self.utf('star')),
r"""    _    __      ___     __      __  _                _____            __                    """,
r"""   | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  _______/ /____  ____ ___      """,
r"""   | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / ___/ __/ _ \/ __ `__ \     """,
r"""   | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ /__  / /_/  __/ / / / / /     """,
r"""   |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__, /____/\__/\___/_/ /_/ /_/      """,
r"""                                                        /____/                               """,
r"""                                                                                            """,
r"""   Copyright {} 2017 Commissariat à l'Énergie Atomique et aux Énergies Alternatives (CEA)   """.format(self.utf('copy')),
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
            self.__print_rawline(click.style("\n".join(logo[0:6]), fg="green"))
            self.__print_rawline(click.style("\n".join(logo[6:7])))
            self.__print_rawline(click.style("\n".join(logo[7:10]), fg="green"))
            self.__print_rawline(click.style("\n".join(logo[10:11]), fg="yellow"))
            self.__print_rawline(click.style("\n".join(logo[11:13]), fg="red"))
            self.__print_rawline(click.style("\n".join(logo[13:])))
