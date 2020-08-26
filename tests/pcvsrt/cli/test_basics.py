import pcvsrt
import pytest
import os
import click
from .cli_testing import run_and_test, isolated_fs
from pcvsrt.helpers import log


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
    print([len(i) for i in res.output.split("\n")])
    assert(max([len(l) for l in res.output]) == click.get_terminal_size()[0])


def test_wrong_command():
    res = run_and_test('wrong_command', success=False)
    assert('No such command' in res.output)