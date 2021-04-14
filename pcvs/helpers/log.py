import click
import os
import textwrap
import pprint
import sys

class IOManager:
    glyphs_dict = {
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
            'full_pg' : click.style("\u2022", bold=True, fg="cyan"),
            'empty_pg' : click.style("\u25E6", bold=True, fg="bright_black"),
            'sep_v' : " \u237F ",
            'sep_h' : "\u23BC"
        }
    }
    
    vb_array = {
        'normal': (0, logging.WARNING),
        'info': (1, logging.INFO),
        'debug': (2, logging.DEBUG)
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

    def __init__(self, verbose, glyphs_enabled, length, logpath="", out=True):
        self.linelength = 93
        self.FORMAT = "%(levelname)s: %(message)s"
        self.wrapper = None
        self.out = out
        self.verbosity = 0
        self.write_logs = False
        self.verbose = verbose
        self.glyphs_enabled = glyphs_enabled
        if glyphs_enabled:
            self.glyphs = self.glyphs_dict["unicode"]
        else:
            self.glyphs = self.glyphs_dict["ascii"]

        if length is not None:
            self.linelength = length if length > 0 else click.get_terminal_size()[0]
        if(logpath!=""):
            self.write_logs = True
            self.logpath = logpath
            self.logfile = open(os.path.join(logpath, "out.log"), "w")
        self.wrapper = textwrap.TextWrapper(width=self.linelength)
    
    def __del__(self):
        if(self.write_logs):
            self.logfile.close()

    def __printlog(self, msg):
        if(self.out):
            click.echo(msg)
        if(self.write_logs):
            self.logfile.write(msg + "\n")

    def get_verbosity(self, match):
        assert(match in self.vb_array.keys())
        return self.vb_array[match][0] <= self.verbosity

    def get_verbosity_str(self):
        for k, v in self.vb_array.items():
            if v[0] == self.verbosity:
                return k

    def print(self, *msg):
        for i in msg:
            self.__printlog(i)
    
    def pcvs_log_raising_exception(self, f):
        def inner(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                self.log_exception(e)

                raise e

        return inner

    def __set_encoding(self, e):
        if(e == "utf-8" or e == "unicode"):
            self.glyphs = self.glyphs_dict["unicode"]
        elif(e == "ascii"):
            self.glyphs = self.glyphs_dict["ascii"]

    # def log_error(msg):
    #     error(msg)
        
    # def log_exception(e):
    #     log("raised exception {}".format(e))

    def utf(self, k):
        assert(k in self.glyphs.keys())
        return self.glyphs[k]

    def print_header(self, s, out=True):
        hdr_char = self.utf('hdr')
        str_len = self.linelength - (len(s) + 2 + 9)  # surrounding spaces  + color ID
        begin = hdr_char * int(str_len / 2)
        end = begin + (hdr_char * (str_len % 2 != 0))

        fs = click.style("{} {} {}".format(begin, s.upper(), end), fg="green")
        if len(fs) > self.linelength:
            fs = click.style("{} {} {}".format(2*hdr_char, s.upper(), 2*hdr_char), fg="green")
        self.wrapper.subsequent_indent = (2*hdr_char) + " "
        fs = self.wrapper.fill(fs)
        if out:
            self.__printlog(fs)
        else:
            return fs
        pass

    def print_section(self, s, out=True):
        f = "{} {}".format(self.utf('sec'), s)
        self.wrapper.subsequent_indent = "  "
        s = self.wrapper.fill(click.style(f, fg='yellow'))
        if out:
            self.__printlog(s)
        else:
            return s

    def print_item(self, s, depth=1, out=True, with_bullet=True):
        indent = ("   " * depth)
        bullet = indent + "{} ".format(self.utf('item')) if with_bullet is True else ""
        content = "{}".format(s)

        self.wrapper.subsequent_indent = indent + "  "
        s = self.wrapper.fill(click.style(bullet, fg="red") + click.style(content, fg="reset"))
        if out:
            self.__printlog(s)
        else:
            return s

    def debug(self, *msg):
        if(self.verbose >= 3):
            for elt in msg:
                for line in elt.split('\n'):
                    self.__printlog("DEBUG: {}".format(click.style(line, fg="bright_black")))


    def info(self, *msg):
        if(self.verbose >= 2):
            for elt in msg:
                for line in elt.split('\n'):
                    self.__printlog("INFO: {}".format(click.style(line, fg="cyan")))


    def warn(self, *msg):
        for elt in msg:
            for line in elt.split('\n'):
                self.__printlog("WARNING: {}".format(click.style(line, fg="yellow", bold=True)))


    def err(self, *msg, abort=1):
        self.__printlog("{}".format(click.style('-' * self.linelength, fg="red", bold=True)))
        for elt in msg:
            for line in elt.split('\n'):
                self.__printlog("ERROR: {}".format(click.style(line, fg="red", bold=True)))
        self.__printlog("{}".format(click.style('-' * self.linelength, fg="red", bold=True)))


    def progbar(self, it, print_func=None, **kargs):
        return click.progressbar(it, empty_char=self.utf('empty_pg'),
                                info_sep=self.utf('sep_v'), fill_char=self.utf('full_pg'),
                                show_percent=False, show_eta=False, show_pos=False,
                                item_show_func=print_func,
                                **kargs)


    def short_banner(self, string=False):
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
        if self.linelength < max(map(lambda x: len(x), logo)):
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
            self.__printlog("\n".join(s))


    def nimpl(self, *msg):
        self.err("This is not implemented (yet)!")  

    def print_n_stop(self, **kwargs):
        for k, v in kwargs.items():
            click.secho("{}: ".format(k), fg="yellow", nl=False)
            click.secho(pprint.pformat(v), fg="blue")
        sys.exit(0)


    def banner(self):
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
            r"""                           """.format(self.utf('star'), utf('star')),
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
            r"""t aux Énergies Alternatives (CEA)   """.format(self.utf('copy')),
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
        if self.linelength < max(map(lambda x: len(x), logo)):
            self.short_banner()
            return
        else:
            click.secho("\n".join(logo[0:6]), fg="green")
            click.secho("\n".join(logo[6:7]))
            click.secho("\n".join(logo[7:9]), fg="green")
            click.secho("\n".join(logo[9:11]), fg="yellow")
            click.secho("\n".join(logo[11:12]), fg="red")
            click.secho("\n".join(logo[12:]))
