import os

import click
from pcvs import BACKUP_NAMEDIR
import pytest
import logging
import pcvs
from pcvs.helpers import log

from .conftest import isolated_fs, click_call


def test_cmd():
    res = click_call()
    assert ('Usage:' in res.output)


def test_version():
    res = click_call('--version')
    assert(res.exit_code == 0)
    assert ("Parallel Computing Validation System (pcvs) -- version" in res.output)


def test_help():
    res = click_call('help')
    assert(res.exit_code == 0)
    assert ('DOCUMENTATION' in res.output)


def test_terminal_size():
    res = click_call('config', 'list')
    assert(res.exit_code == 0)
    for line in res.output:
        assert(len(line) <= log.linelength)
    
    res = click_call('-w 20', 'config', 'list')
    assert(res.exit_code == 0)
    for line in res.output:
        assert(len(line) <= 20)

    res = click_call('-w 0', 'config', 'list')
    assert(res.exit_code == 0)
    assert(max([len(l) for l in res.output.split('\n')]) == click.get_terminal_size()[0])


def test_verbosity(caplog):
    caplog.set_level(logging.DEBUG)
    res = click_call('-vv', 'config', 'list')
    assert(res.exit_code == 0)
    print(caplog.text)
    assert('Scopes are ordered as follows' in caplog.text)


def test_local_path(caplog):
    caplog.set_level(logging.DEBUG)
    with isolated_fs():
        res = click_call('-v', 'config', 'list')
        assert("LOCAL: " + os.getcwd() + '/' + BACKUP_NAMEDIR in caplog.text)


def test_bad_command():
    res = click_call('wrong_command')
    assert(res.exit_code != 0)
    assert('No such command' in res.output)
