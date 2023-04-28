import functools
import logging
import os
import shutil
import sys
import enum
from datetime import datetime
import click
import rich
import rich.box as box
from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TextColumn,
                           TimeElapsedColumn, track)
from rich.table import Table
from rich.theme import Theme

import pcvs


class SpecialChar:
    copy = '\u00A9'
    item = '\u27E2'
    sec = '\u2756'
    hdr = '\u23BC'
    star = '\u2605'
    fail = '\u2718'
    succ = '\u2714'
    none = '\u2205'
    git = '\u237F'
    time = '\U0000231A'
    sep_v = " \u237F "
    sep_h = "\u23BC"

    def __init__(self, utf_support=True):
        if not utf_support:
            self.copy = '(c)'
            self.item = '*'
            self.sec = '#'
            self.hdr = '='
            self.star = "*"
            self.fail = 'X'
            self.succ = 'V'
            self.none = '-'
            self.git = '(git)'
            self.time = '(time)'
            self.sep_v = " | "
            self.sep_h = "-"

class Verbosity(enum.IntEnum):
    COMPACT = 0
    DETAILED = 1
    INFO = 2
    DEBUG = 3
    NB_LEVELS = enum.auto()
    
    def __str__(self):
        return self.name
    
class TheConsole(Console):

    def __init__(self, *args, **kwargs):
        self._color = "auto" if kwargs.get('color', True) else None
        self._verbose = Verbosity(min(Verbosity.NB_LEVELS -1, kwargs.get('verbose', 0)))
        self._debugfile = open(os.path.join(".", pcvs.NAME_DEBUG_FILE), "w")
        self.summary_table = dict()
        err = kwargs.get('stderr', False)
        log_level = "DEBUG" if self._verbose else "INFO"
        theme = Theme({
            "warning": "bold yellow",
            "danger": "bold red"
        })

        super().__init__(color_system=self._color, theme=theme, stderr=err)
        self._debugconsole = Console(file=self._debugfile, theme=theme,
                                     color_system=self._color,
                                     markup=self._color is not None)

        logging.basicConfig(
            level=log_level, format="%(message)s",
            handlers=[RichHandler(
                                  console=self._debugconsole,
                                  omit_repeated_times=False,
                                  rich_tracebacks=True,
                                  show_level=True,
                                  tracebacks_suppress=[click],
                                  show_path=True)])
        self._loghdl = logging.getLogger("pcvs")
        self._chars = SpecialChar(utf_support=(
            self.encoding.startswith('utf')))

    @property
    def logfile(self):
        return os.path.abspath(self._debugfile.name)
    
    @property
    def outfile(self):
        return os.path.abspath(self.file.name)
    @property
    def verbose(self):
        return self._verbose

    def verb_level(self, level):
        return self._verbose >= level 
    
    @property
    def verb_compact(self):
        return self.verb_level(Verbosity.COMPACT)
    
    @property
    def verb_detailed(self):
        return self.verb_level(Verbosity.DETAILED)
    
    @property
    def verb_info(self):
        return self.verb_level(Verbosity.INFO)
    
    @property
    def verb_debug(self):
        return self.verb_level(Verbosity.DEBUG)

    @verbose.setter
    def verbose(self, v):
        self._verbose = v

    def __del__(self):
        if self._debugfile:
            self._debugfile.close()
            self._debugfile = None

    def move_debug_file(self, newdir):
        assert (os.path.isdir(newdir))
        if self._debugfile:
            shutil.move(self._debugfile.name, os.path.join(
                newdir, pcvs.NAME_DEBUG_FILE))
        else:
            self.warning("No '{}' file found for this Console".format(
                pcvs.NAME_DEBUG_FILE))

    def print_section(self, txt):
        self.print("[yellow bold]{} {}[/]".format(self.utf('sec'), txt))
        self.info("[DISPLAY] ======= {} ======".format(txt))

    def print_header(self, txt):
        self.rule("[green bold]{}[/]".format(txt.upper()))
        self.info("[DISPLAY] ------- {} ------".format(txt))

    def print_item(self, txt, depth=1):
        self.print("[red bold]{}{}[/] {}".format(" " *
                   (depth*2), self.utf('item'), txt))
        self.info("[DISPLAY] * {}".format(txt))

    def print_box(self, txt, *args, **kwargs):
        self.print(Panel.fit(txt, *args, **kwargs))

    def print_job(self, state, time, tlabel, tsubtree, tname, colorname="red", icon=None, content=None):
        if icon is not None:
            icon = self.utf(icon)

        if self._verbose >= Verbosity.DETAILED:
            self.print("[{} bold]   {} {:8.2f}s{}{:7}{}{}".format(
                colorname,
                icon,
                time,
                self.utf("sep_v"),
                state,
                self.utf("sep_v"),
                tname)
            )
            if content:
                # print raw input
                # parsing on uncontrolled output may lead to errors
                self.out(content)
        else:
            self.summary_table.setdefault(tlabel, {})
            self.summary_table[tlabel].setdefault(tsubtree, {
                l: 0 for l in ["SUCCESS", "FAILURE", "ERR_DEP", "ERR_OTHER"]
            })

            self.summary_table[tlabel][tsubtree][state] += 1

            def regenerate_table():
                table = Table(expand=True, box=box.SIMPLE)
                table.add_column("Name", justify="left", ratio=10)
                table.add_column("SUCCESS", justify="center")
                table.add_column("FAILURE", justify="center")
                table.add_column("ERROR", justify="center")
                table.add_column("OTHER", justify="center")
                for l, lv in self.summary_table.items():
                    for s, sv in lv.items():
                        if sum(sv.values()) == sv.get('SUCCESS', 0):
                            c = "green"
                        elif sv.get('FAILURE', 0) > 0:
                            c = "red"
                        else:
                            c = "yellow"
                        columns_list = ["[{} bold]{}".format(
                            c, x) for x in sv.values()]
                        table.add_row(
                            "[{} bold]{}{}".format(c, l, s),
                            *columns_list
                        )
                return table

            self._reset_display_table(regenerate_table())
        self._progress.advance(self._singletask)
        self.live.update(self._display_table)

    def _reset_display_table(self, table):
        self._display_table = Table.grid(expand=True)
        self._display_table.add_row(table)
        self._display_table.add_row(Panel(self._progress))

    def table_container(self, total) -> Live:
        self._progress = Progress(
            TimeElapsedColumn(),
            "Progress",
            BarColumn(bar_width=None, complete_style="yellow",
                      finished_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            SpinnerColumn(speed=0.5),
            expand=True)
        self._singletask = self._progress.add_task(
            "Progress", total=int(total))

        self._reset_display_table(Table())
        self.live = Live(self._display_table, console=self)
        return self.live

    def create_table(self, title, cols):
        return Table(*cols, title=title)

    def progress_iter(self, it, **kwargs):
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
        global console
        return track(it, transient=True, console=console,
                     complete_style="cyan",
                     pulse_style="green",
                     refresh_per_second=4,
                     description="[red]In Progress...[red]",
                     **kwargs)

    def utf(self, k):
        return getattr(self._chars, k)

    def print_banner(self):

        logo_minimal = [
            r"""[green]{}""".format(self.utf('star') * 19),
            r"""[yellow]     -- PCVS --  """,
            r"""[red]{} CEA {} 2017-{} {}""".format(
                self.utf('star'), self.utf('copy'), datetime.now().year, self.utf('star')),
            r"""[green]{}""".format(self.utf('star') * 19)
        ]

        logo_short = [
            r"""[green  ]     ____    ______  _    __  _____""",
            r"""[green  ]    / __ \  / ____/ | |  / / / ___/""",
            r"""[green  ]   / /_/ / / /      | | / /  \__ \ """,
            r"""[yellow ]  / ____/ / /___    | |/ /  ___/ / """,
            r"""[red    ] /_/      \____/    |___/  /____/  """,
            r"""[red    ]                                   """,
            r"""[default] Parallel Computing -- Validation System""",
            r"""[default] Copyright {} 2017-{} -- CEA""".format(
                self.utf('copy'), datetime.now().year),
            r""""""
        ]

        logo = [
            r"""[green  ]     ____                   ____     __   ______                            __  _             """,
            r"""[green  ]    / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _ """,
            r"""[green  ]   / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/ """,
            r"""[green  ]  / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ /  """,
            r"""[green  ] /_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /   """,
            r"""[green  ]                                                           /_/                     /____/     """,
            r"""[default]                                            {} ([link=https://pcvs.io]PCVS[/link]) {}""".format(
                self.utf('star'), self.utf('star')),
            r"""[green  ]    _    __      ___     __      __  _                _____            __                    """,
            r"""[green  ]   | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  _______/ /____  ____ ___      """,
            r"""[green  ]   | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / ___/ __/ _ \/ __ `__ \     """,
            r"""[yellow ]   | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ /__  / /_/  __/ / / / / /     """,
            r"""[red    ]   |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__, /____/\__/\___/_/ /_/ /_/      """,
            r"""[red    ]                                                        /____/                               """,
            r"""[red    ]                                                                                             """,
            r"""[default]  Copyright {} 2017-{} Commissariat à l'Énergie Atomique et aux Énergies Alternatives ([link=https://cea.fr]CEA[/link])""".format(
                self.utf('copy'), datetime.now().year),
            r"""[default]                                                                                             """,
            r"""[default]  This program comes with ABSOLUTELY NO WARRANTY;""",
            r"""[default]  This is free software, and you are welcome to redistribute it""",
            r"""[default]  under certain conditions; Please see COPYING for details.""",
            r"""[default]                                                                                             """,
        ]
        banner = logo
        
        if self.size.width < 40:
            banner = logo_minimal
        elif self.size.width < 95:
            banner = logo_short

        self.print("\n".join(banner))

    def info(self, fmt, *args, **kwargs):
        self._loghdl.info(fmt, *args, **kwargs)

    def debug(self, fmt, *args, **kwargs):
        self._loghdl.debug(fmt, *args, **kwargs)

    def warning(self, fmt, *args, **kwargs):
        self._loghdl.warning(fmt, *args, **kwargs)

    def warn(self, fmt, *args, **kwargs):
        self.warning(fmt, *args, **kwargs)
        #self.print(
        #    "[warning]WARN: {}[/warning]".format(fmt.format(*args, **kwargs)), )

    def error(self, fmt, *args, **kwargs):
        self._loghdl.error(fmt, *args, **kwargs)
        self.print(
            "[danger]ERROR: {}[/danger]".format(fmt.format(*args, **kwargs)))

    def critical(self, fmt, *args, **kwargs):
        self._loghdl.critical(fmt, *args, **kwargs)
        self.print(
            "[danger]CRITICAL: {}[/danger]".format(fmt.format(*args, **kwargs)))
        sys.exit(42)

    def exception(self, e: BaseException, *args, **kwargs):
        if self._verbose >= Verbosity.INFO:
            self.print_exception(suppress=['click'])
        self._loghdl.exception(e)

    @property
    def logger(self):
        return self._loghdl

console = None


def init(color=True, verbose=0, *args, **kwargs):
    global console
    console = TheConsole(color=color, verbose=verbose, *args, **kwargs)


def detach_console():
    global console
    logfile = os.path.join(os.path.dirname(console.logfile), pcvs.NAME_LOG_FILE)
    console.file = open(logfile, 'w')
    

def capture_exception(e_type, user_func=None):
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
                if user_func is None:
                    global console
                    if not console:
                        console = TheConsole()
                    console.exception(e)
                    console.print("[red bold]Exception: {}[/]".format(e))
                    console.print(
                        "[red bold]See '{}' or rerun with -vv for more details[/]".format(pcvs.NAME_DEBUG_FILE))
                    sys.exit(1)
                else:
                    user_func(e)
        return wrapper
    return inner_function
