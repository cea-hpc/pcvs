import pcvsrt
import pytest
import os
from .cli_testing import run_and_test, isolated_fs


def test_cmd():
    res = run_and_test()
    assert ('Usage:' in res.output)


def test_version():
    res = run_and_test('--version')
    assert ("PCVS Runtime Tool (pcvs-rt) -- version" in res.output)


def test_help():
    res = run_and_test('help')
    assert ('DOCUMENTATION' in res.output)


def test_wrong_command():
    res = run_and_test('wrong_command', success=False)
    assert('No such command' in res.output)