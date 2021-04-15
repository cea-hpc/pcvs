import logging
import os

import click
import pytest

import pcvs
from pcvs import NAME_SRCDIR
from pcvs.helpers import log

from .conftest import click_call, isolated_fs


def test_cmd():
    res = click_call()
    assert ('Usage:' in res.stderr)


def test_version():
    res = click_call('--version')
    assert(res.exit_code == 0)
    assert ("Parallel Computing Validation System (pcvs) -- version" in res.output)


def test_help():
    res = click_call('help')
    assert(res.exit_code == 0)
    assert ('DOCUMENTATION' in res.stdout)

def test_bad_command():
    res = click_call('wrong_command')
    assert(res.exit_code != 0)
    assert('Error: No such command' in res.stderr)
