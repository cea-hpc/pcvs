import functools
import os
import pprint
import sys
import textwrap
import traceback

import click

from pcvs import io
from pcvs.helpers import exceptions
from pcvs.helpers.exceptions import CommonException


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
    manager = io.console

    if man is None:
        man = manager

    # return click.progressbar(
    #    it, empty_char=man.utf('empty_pg'),
    #    info_sep=man.utf('sep_v'), fill_char=man.utf('full_pg'),
    #    sh_percent=False, show_eta=False, show_pos=False,
    #    item_show_func=print_func,
    #    **kargs)
