import os

import click
import pytest
import logging
import pcvsrt
from pcvsrt.helpers import log

from .cli_testing import isolated_fs, run_and_test


def test_cmd():
    res = run_and_test()
    assert ('Usage:' in res.output)


def test_version():
    res = run_and_test('--version')
    assert ("PCVS Runtime Tool (pcvs-rt) -- version" in res.output)


def test_help():
    res = run_and_test('help')
    assert ('DOCUMENTATION' in res.output)


def test_terminal_size():
    res = run_and_test('config', 'list')
    for line in res.output:
        assert(len(line) <= log.linelength)
    
    res = run_and_test('-w 20', 'config', 'list')
    for line in res.output:
        assert(len(line) <= 20)

    res = run_and_test('-w 0', 'config', 'list')
    assert(max([len(l) for l in res.output.split('\n')]) == click.get_terminal_size()[0])


def test_verbosity(caplog):
    caplog.set_level(logging.DEBUG)
    res = run_and_test('-vv', 'config', 'list')
    print(caplog.text)
    assert('Scopes are ordered as follows' in caplog.text)


def test_local_path(caplog):
    caplog.set_level(logging.DEBUG)
    with isolated_fs():
        res = run_and_test('-v', 'config', 'list')
        assert("LOCAL: " + os.getcwd() + '/.pcvsrt' in caplog.text)


def test_bad_command():
    res = run_and_test('wrong_command', success=False)
    assert('No such command' in res.output)
