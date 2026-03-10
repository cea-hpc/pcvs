import atexit
import enum
import functools
import logging
import os
import shutil
import sys
from datetime import datetime
from importlib.metadata import version
from logging import Logger
from typing import Any
from typing import Callable
from typing import IO
from typing import Iterable
from typing import Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TaskID
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import track
from rich.style import Style
from rich.table import Column
from rich.table import Table
from rich.theme import Theme

import pcvs
from pcvs.testing.teststate import TestState


class SpecialChar:
    """
    Class mapping special char display.

    Enabled or disabled according to utf support.
    """

    copy = "\u00a9"
    item = "\u27e2"
    sec = "\u2756"
    hdr = "\u23bc"
    star = "\u2605"
    fail = "\u2718"
    succ = "\u2714"
    none = "\u2205"
    git = "\u237f"
    time = "\U0000231a"
    sep_v = " \u237f "
    sep_h = "\u23bc"

    def __init__(self, utf_support: Optional[bool] = True):
        """
        Initialize a new char handler depending on utf support

        :param utf_support: support for utf encoding, defaults to True
        """
        if not utf_support:
            self.copy = "(c)"
            self.item = "*"
            self.sec = "#"
            self.hdr = "="
            self.star = "*"
            self.fail = "X"
            self.succ = "V"
            self.none = "-"
            self.git = "(git)"
            self.time = "(time)"
            self.sep_v = " | "
            self.sep_h = "-"


class Verbosity(enum.IntEnum):
    """
    Enum to map a verbosity level to a more
    convenient label.

    * COMPACT: compact way, jobs are displayed packed per input YAML file.
    * DETAILED: each job will output result on a one-line manner.
    * INFO: DETAILED & INFO messages will be logged.
    * LOG: DETAILED & INFO & LOG messages will be logged.
    * DEBUG: DETAIL, INFO, LOG & DEBUG messages, with more infos in stack traces.
    """

    COMPACT = 0
    DETAILED = 1
    INFO = 2
    LOG = 3
    DEBUG = 4
    NB_LEVELS = enum.auto()

    def __str__(self) -> str:
        """
        Convert object to human-readable string

        :return: a verbosity as printable string
        """
        return self.name


class PCVSConsole:
    """
    Main interface to print information to users.

    Any output from the application should be handled by this Console.
    """

    def __init__(self, color: bool = True, verbose: int = 0):
        """
        Build a new Console:
        - color: boolean (color support)
        - verbose: boolean (verbose msg mode in log files)
        Any other argument is considered a base class options.

        :param color: should the console use color.
        :param verbose: verbosity level of the console.
        """
        self._progress: Progress | None = None
        self._singletask: TaskID | None = None
        self._live: Live | None = None

        # should we use color
        self._color: bool = color
        # verbosity level
        self._verbosity: Verbosity = Verbosity(min(Verbosity.NB_LEVELS - 1, verbose))

        # debug file path
        self._debugfile_path: str = os.path.join(".", pcvs.NAME_DEBUG_FILE)
        # should we delete debug file on exit
        self._delete_debugfile_on_exit: bool = self._verbosity < Verbosity.DEBUG
        atexit.register(self.delete_debug_file)

        self.job_summary_data_table: dict[str, dict[str, dict[str, int]]] = {}
        # https://rich.readthedocs.io/en/stable/appendix/colors.html#appendix-colors
        theme: Theme = Theme(
            {
                "debug": Style(color="white"),
                "log": Style(color="white"),
                "info": Style(color="bright_white"),
                "warning": Style(color="yellow", bold=True),
                "danger": Style(color="red", bold=True),
            }
        )
        color_system = "auto" if self._color else None
        self._stdout: Console = Console(color_system=color_system, theme=theme)  # type: ignore
        self._stderr: Console = Console(color_system=color_system, theme=theme, stderr=True)  # type: ignore

        # logging management for debug file:
        # Logger
        self._loghdl: Logger = logging.getLogger("pcvs")
        self._loghdl.setLevel(logging.DEBUG)
        # Formatter
        formatter: logging.Formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        # File handler
        file_handler: logging.FileHandler = logging.FileHandler(self._debugfile_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        # TODO: replace rich logger with logging
        # Console handler
        # console_handler = logging.StreamHandler()
        # console_handler.setLevel(logging.INFO)
        # console_handler.setFormatter(formatter)
        # Add handlers to logger
        self._loghdl.addHandler(file_handler)
        # logger.addHandler(console_handler)

        self._chars: SpecialChar = SpecialChar(utf_support=self._stdout.encoding.startswith("utf"))

        # Activate when needed
        self._sched_debug: bool = False
        self._crit_debug: bool = False

    def delete_debug_file(self) -> None:
        self.debug(f"deleting log file: {self._debugfile_path}")
        if self._delete_debugfile_on_exit:
            if os.path.isfile(self._debugfile_path):
                os.remove(self._debugfile_path)

    # log file management

    @property
    def logfile(self) -> str:
        """
        Get the path to the logging file.

        :return: the logging file
        """
        return os.path.abspath(self._debugfile_path)

    @property
    def outfile(self) -> str:
        """
        Get the path where the Console output is logged (disabled by default).

        :return: the file path
        """
        return os.path.abspath(self._stdout.file.name)

    def setoutfile(self, file: IO[str]) -> None:
        self._stdout.file = file
        self._stderr.file = file

    def move_debug_file(self, newdir: str) -> None:
        assert os.path.isdir(newdir)
        if self._debugfile_path and os.path.exists(self._debugfile_path):
            shutil.move(self._debugfile_path, os.path.join(newdir, pcvs.NAME_DEBUG_FILE))
        else:
            self.warning("No '{}' file found for this Console".format(pcvs.NAME_DEBUG_FILE))

    # Verbosity

    @property
    def verbosity(self) -> int:
        """Return the Verbosity level."""
        return self._verbosity

    @verbosity.setter
    def verbosity(self, v: Verbosity) -> None:
        """Set Verbosity level."""
        self._verbosity = v

    # Standard printers

    def nodebug(self, fmt: str) -> None:
        """Do nothing, place holder to remove debug print without deleting lines."""

    def debug(self, fmt: str) -> None:
        """Print debug."""
        self._loghdl.debug(fmt)
        if self._verbosity >= Verbosity.DEBUG:
            self._stdout.print(f"[debug]\\[debug] {fmt}[/debug]", soft_wrap=True)

    def log(self, fmt: str) -> None:
        """Print log."""
        self._loghdl.debug(fmt)
        if self._verbosity >= Verbosity.LOG:
            self._stdout.print(f"[debug]\\[log] {fmt}[/debug]", soft_wrap=True)

    def info(self, fmt: str) -> None:
        """Print info."""
        self._loghdl.info(fmt)
        if self._verbosity >= Verbosity.INFO:
            self._stdout.print(f"[info]\\[info] {fmt}[/info]", soft_wrap=True)

    def warning(self, fmt: str) -> None:
        """Print warning."""
        self._loghdl.warning(fmt)
        self._stderr.print(f"[warning]\\[warning] {fmt}[/warning]", soft_wrap=True)

    def warn(self, fmt: str) -> None:
        """Short for warning."""
        self.warning(fmt)

    def error(self, fmt: str) -> None:
        """Print an error messages."""
        self._loghdl.error(fmt)
        self._stderr.print(f"[danger]\\[error] {fmt}[/danger]", soft_wrap=True)

    def critical(self, fmt: str) -> None:
        """Print a log critical error then exit."""
        self._loghdl.critical(fmt)
        self._stderr.print(f"[danger]\\[CRITICAL] {fmt}[/danger]", soft_wrap=True)
        sys.exit(42)

    def exception(self, e: Exception) -> None:
        """Print exceptions."""
        # do not delete debug file if we have logged exceptions
        self._delete_debugfile_on_exit = False
        self._stderr.print("\n")
        if self._verbosity >= Verbosity.DEBUG:
            self._stderr.print_exception(word_wrap=True, show_locals=True, extra_lines=16)
        elif self._verbosity >= Verbosity.LOG:
            self._stderr.print_exception(extra_lines=3)
        else:
            self._stderr.print(
                "[warning]\\[Exception] Stack trace hidden, to get a stack trace, "
                "look at 'pcvs-debug-*.log' or rerun pcvs with '-vvv' or '-d'.[/warning]"
            )
        self._stderr.print(f"[danger]\\[Exception] {e}[/danger]", soft_wrap=True)
        self._loghdl.exception(e)

    def crit_debug(self, fmt: str) -> None:
        """Print & log debug for pcvs criterions."""
        if self._crit_debug:
            self.debug(f"[CRIT]{fmt}")

    def sched_debug(self, fmt: str) -> None:
        """Print & log debug for pcvs scheduler."""
        if self._sched_debug:
            self.debug(f"[SCHED]{fmt}")

    @property
    def logger(self) -> Logger:
        """Get Logger."""
        return self._loghdl

    # Other printers

    def print(self, fmt: str = "") -> None:
        """Print a line to stdout."""
        self._stdout.print(fmt)
        self._loghdl.info("[PRINT] %s", fmt)

    def print_section(self, txt: str) -> None:
        """Print Section."""
        self._stdout.print("[yellow bold]{} {}[/]".format(self.utf("sec"), txt), soft_wrap=True)
        self._loghdl.info("[DISPLAY] ======= %s ======", txt)

    def print_header(self, txt: str) -> None:
        """Print Header."""
        self._stdout.rule("[green bold]{}[/]".format(txt.upper()))
        self._loghdl.info("[DISPLAY] ------- %s ------", txt)

    def print_item(self, txt: str, depth: int = 1) -> None:
        """Print Item."""
        self._stdout.print(
            "[red bold]{}{}[/] {}".format(" " * (depth * 2), self.utf("item"), txt), soft_wrap=True
        )
        self._loghdl.info("[DISPLAY] * %s", txt)

    def print_box(self, txt: str, panel_options: dict) -> None:
        """Print a Box."""
        panel_box = Panel.fit(txt, **panel_options)
        self._stdout.print(panel_box)
        self._loghdl.info("[DISPLAY] BOX %s", panel_box)

    def print_rich(self, to_print: Any) -> None:
        """Print rich formatted object."""
        # logging to self._loghdl would be useless as we would just get python object ref.
        self._stdout.print(to_print)

    # Others

    def _get_display_table(self, include_jobs: bool = False) -> Table:
        """
        Get the table to display for live update.

        Include the progress bar, may include the job view table.

        :param include_jobs: should the list of jobs be added to the progress table.
        :return: Return the built table.
        """
        table = Table.grid(expand=True)
        if include_jobs:
            table.add_row(self._get_job_table())
        else:
            # Add spacing
            table.add_row()
        table.add_row(self._progress)
        return table

    def _get_job_table(self) -> Table:
        """Transform the job data table into a job view table."""
        table = Table(expand=True, box=box.SIMPLE)
        table.add_column("Name", justify="left", ratio=10)
        for state in TestState.all_states():
            table.add_column(str(state), justify="right")
        for label, lvalue in sorted(self.job_summary_data_table.items()):
            for subtree, svalue in sorted(lvalue.items()):
                if sum(svalue.values()) == svalue.get("SUCCESS", 0):
                    colour = "green"
                elif svalue.get("FAILURE", 0) > 0:
                    colour = "red"
                else:
                    colour = "yellow"
                columns_list = [f"[{colour} bold]{x}" for x in svalue.values()]
                table.add_row(f"[{colour} bold]{label}{subtree}", *columns_list)
        return table

    def _insert_job_table(self, state: TestState, test_label: str, test_subtree: str) -> None:
        """
        Insert a job in the job data table.

        This job table is display when running on low verbosity level
        or at the end of the run.

        :param state: The exit state of the test
        :param test_label: The label of the test
        :param test_subtree: The sub directory of the test
        """
        self.job_summary_data_table.setdefault(test_label, {})
        self.job_summary_data_table[test_label].setdefault(
            test_subtree,
            {str(label): 0 for label in TestState.all_states()},
        )
        self.job_summary_data_table[test_label][test_subtree][str(state)] += 1

    def print_job(
        self, status: str, state: TestState, tlabel: str, tsubtree: str, content: str | None = None
    ) -> None:
        """Print a Job.

        If Verbosity level is equal or above Verbosity.DETAILED, print each tests.
        Otherwise, print a summary block.
        Optionally print raw test result content.

        :param status: The status line indicating test information
        :param state: The status of the printed test
        :param tlabel: The label of the test.
        :param tsubtree: Thr sub directory of the test
        :param content: stdout/stderr of the test, if specify
        """
        # Update Job data table state.
        self._insert_job_table(state, tlabel, tsubtree)
        # Update progress bar state.
        assert self._progress is not None
        assert self._singletask is not None
        self._progress.advance(self._singletask)
        # always log status to log file
        self._loghdl.debug(status)
        if self.verbosity >= Verbosity.DETAILED:
            # Print the test status line.
            self._stdout.print(status)
            if content:
                # Print raw test output.
                self._stdout.out(content)
        # Update the table/progressbar display.
        assert self._live is not None
        self._live.update(self._get_display_table(self._verbosity <= Verbosity.COMPACT))

    def print_job_summary(self) -> None:
        """Print the job view table once."""
        self._stdout.print(self._get_job_table())

    def table_container(self, total: int) -> Live:
        """The main pcvs run progress bar that may include job summary."""
        self._progress = Progress(
            TimeElapsedColumn(),
            "Progress",
            BarColumn(bar_width=None, complete_style="yellow", finished_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            SpinnerColumn(speed=0.5),
            expand=True,
        )
        self._singletask = self._progress.add_task("Progress", total=int(total))
        self._live = Live(self._get_display_table(False), console=self._stdout)
        return self._live

    def create_table(self, title: str, cols: list[Column]) -> Table:
        """Create and return a rich table."""
        return Table(*cols, title=title)

    def progress_iter(self, it: Iterable) -> Iterable:
        """Print a progress bar using click.

        :param it: iterable on which the progress bar has to iterate
        :return: a click progress bar (iterable)
        """
        return track(
            it,
            transient=True,
            console=self._stdout,
            complete_style="cyan",
            pulse_style="green",
            refresh_per_second=4,
            description="[red]In Progress...[red]",
        )

    def utf(self, k: str) -> str:
        """
        Return the encoding supported by this session for the given key.

        :param k: the key as defined by SpecialChar
        :return: the associated printable sequence
        """
        char = getattr(self._chars, k)
        assert isinstance(char, str)
        return char

    def print_banner(self) -> None:
        """
        Print the PCVS logo fitting with current terminal size
        """

        logo_minimal = [
            r"""[green]{}""".format(self.utf("star") * 19),
            r"""[yellow]     -- PCVS --  """,
            r"""[red]{} CEA {} 2017-{} {}""".format(
                self.utf("star"), self.utf("copy"), datetime.now().year, self.utf("star")
            ),
            r"""[green]{}""".format(self.utf("star") * 19),
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
                self.utf("copy"), datetime.now().year
            ),
            r"""""",
        ]

        logo = [
            r"""[green  ]     ____                   ____     __   ______                            __  _             """,
            r"""[green  ]    / __ \____ __________ _/ / /__  / /  / ____/___  ____ ___  ____  __  __/ /_(_)___  ____ _ """,
            r"""[green  ]   / /_/ / __ `/ ___/ __ `/ / / _ \/ /  / /   / __ \/ __ `__ \/ __ \/ / / / __/ / __ \/ __ `/ """,
            r"""[green  ]  / ____/ /_/ / /  / /_/ / / /  __/ /  / /___/ /_/ / / / / / / /_/ / /_/ / /_/ / / / / /_/ /  """,
            r"""[green  ] /_/    \__,_/_/   \__,_/_/_/\___/_/   \____/\____/_/ /_/ /_/ .___/\__,_/\__/_/_/ /_/\__, /   """,
            r"""[green  ]                                                           /_/                     /____/     """,
            r"""[default]                                            {} ([link=https://pcvs.io]PCVS[/link]) {}""".format(
                self.utf("star"), self.utf("star")
            ),
            r"""[green  ]    _    __      ___     __      __  _                _____            __                    """,
            r"""[green  ]   | |  / /___ _/ (_)___/ /___ _/ /_(_)___  ____     / ___/__  _______/ /____  ____ ___      """,
            r"""[green  ]   | | / / __ `/ / / __  / __ `/ __/ / __ \/ __ \    \__ \/ / / / ___/ __/ _ \/ __ `__ \     """,
            r"""[yellow ]   | |/ / /_/ / / / /_/ / /_/ / /_/ / /_/ / / / /   ___/ / /_/ /__  / /_/  __/ / / / / /     """,
            r"""[red    ]   |___/\__,_/_/_/\__,_/\__,_/\__/_/\____/_/ /_/   /____/\__, /____/\__/\___/_/ /_/ /_/      """,
            r"""[red    ]                                                        /____/                               """,
            r"""[red    ]                                                                                             """,
            r"""[default]  Copyright {} 2017-{} Commissariat à l'Énergie Atomique et aux Énergies Alternatives ([link=https://cea.fr]CEA[/link])""".format(
                self.utf("copy"), datetime.now().year
            ),
            r"""[default]                                                                                             """,
            r"""[default]  This program comes with ABSOLUTELY NO WARRANTY;""",
            r"""[default]  This is free software, and you are welcome to redistribute it""",
            r"""[default]  under certain conditions; Please see COPYING for details.""",
            r"""[default]                                                                                             """,
        ]
        banner = logo

        if self._stdout.size.width < 40:
            banner = logo_minimal
        elif self._stdout.size.width < 95:
            banner = logo_short

        self._stdout.print("\n".join(banner))
        pcvs_version = version("pcvs")
        self._stdout.print(f"Parallel Computing Validation System (pcvs) -- version {pcvs_version}")


console: PCVSConsole = None  # type: ignore  # pylint: disable=invalid-name


def init(color: bool = True, verbose: int = 0) -> None:
    """Init the PCVS Console."""
    global console
    console = PCVSConsole(color=color, verbose=verbose)


def detach_console() -> None:
    """Detach the PCVS Console."""
    logfile = os.path.join(os.path.dirname(console.logfile), pcvs.NAME_LOG_FILE)
    console.setoutfile(open(logfile, "w", encoding="utf-8"))


def capture_exception(
    e_type: Any, user_func: Optional[Callable[[Exception], None]] = None, doexit: bool = True
) -> Callable[[Callable], Callable[[Any], Any]]:
    """
    Wraps functions to capture unhandled exceptions for high-level function not to crash.

    :param e_type: errors to be caught
    :param user_func: Optional, a function to call to manage the exception
    :param doexit: Optional, should pcvs exit after printing the error
    :return: function handler to manage exception
    """

    def inner_function(func: Callable[[...], Any]) -> Callable[[...], Any]:  # type: ignore
        """wrapper for inner function using try/except to avoid crashing

        :param func: function to wrap
        :return: wrapper
        """

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """functools wrapping function

            :param args: arguments forwarded to wrapped func
            :param kwargs: arguments forwarded  to wrapped func
            :return: result of wrapped function
            """
            try:
                return func(*args, **kwargs)
            except e_type as e:
                if user_func is None:
                    assert console is not None
                    console.exception(e)
                    if doexit:
                        sys.exit(1)
                else:
                    return user_func(e)
            return None

        return wrapper

    return inner_function
