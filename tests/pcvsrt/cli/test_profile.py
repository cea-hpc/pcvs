from .conftest import run_and_test, isolated_fs
import pytest


def test_cmd():
    res = run_and_test('profile')
    assert('Usage:' in res.output)


@pytest.mark.parametrize('scope', [None, 'local'])
def test_list(scope, caplog):
    token = "" if scope is None else scope
    _ = run_and_test('profile', 'list', token)

    if scope:
        caplog.clear()
        _ = run_and_test('profile', 'list', token+".test")
        assert ("no LABEL required for this command" in caplog.text)


def test_list_wrong(caplog):
    _ = run_and_test('profile', 'list', 'error', success=False)
    assert ('Invalid SCOPE' in caplog.text)
    _ = run_and_test('profile', 'list', 'failure.extra.field', success=False)
    assert ('Invalid token' in caplog.text)


@pytest.mark.parametrize('scope', [None, 'local'])
def test_build(scope, caplog, mock):
    #mock.patch.object(pvConfig.ConfigurationBlock, )
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default')


def test_build_wrong(caplog):
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default', success=False)
        assert("configuration blocks are required to build" in caplog.text)


def test_destroy(caplog):
    with isolated_fs():
        _ = run_and_test('profile', 'build', 'local.default1')
        _ = run_and_test('profile', 'destroy', 'local.default1', success=False)
        _ = run_and_test('profile', 'destroy', '-f', 'local.default1')
        
        caplog.clear()
        _ = run_and_test('profile', 'destroy', '-f', 'local.default1', success=False)
        assert("not found!" in caplog.text)
