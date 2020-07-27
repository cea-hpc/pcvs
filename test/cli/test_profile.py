from click.testing import CliRunner
from pcvsrt.scripts.cmd import cli
import pcvsrt
import pytest
from testing import run_and_test, isolated_fs


def test_cmd():
    _ = run_and_test('profile')


@pytest.mark.parametrize('scope', [None, 'local'])
def test_list(scope, caplog):
    token = "" if scope is None else scope
    _ = run_and_test('profile', 'list', token)

    if scope:
        caplog.clear()
        _ = run_and_test('profile', 'list', token+".test")
        assert ("no LABEL required for this command" in caplog.text)


def test_list_wrong_scope(caplog):
    _ = run_and_test('profile', 'list', 'error', success=False)
    assert ('Invalid SCOPE' in caplog.text)


def test_build_wrong_args(caplog):
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default', success=False)
        assert("configuration blocks are required to build" in caplog.text)


def test_build(caplog):
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default')


def test_destroy(caplog):
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default1')
        _ = run_and_test('profile', 'destroy', 'local.default1', success=False)
        _ = run_and_test('profile', 'destroy', '-f', 'local.default1')
        
        caplog.clear()
        _ = run_and_test('profile', 'destroy', '-f', 'local.default1', success=False)
        assert("not found!" in caplog.text)
