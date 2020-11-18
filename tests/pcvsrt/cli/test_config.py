import pcvsrt
import pytest
import os
from .conftest import run_and_test, isolated_fs

@pytest.fixture(params=[None] + pcvsrt.cli.cli_config.backend.CONFIG_BLOCKS)
def config_kind(request):
    return request.param

@pytest.fixture(params=[None] + pcvsrt.helpers.utils.storage_order())
def config_scope(request):
    return request.param

class config_mocker:
    pass

def test_cmd():
    res = run_and_test('config')
    assert('Usage:' in res.output)



def test_list_all(config_scope, caplog):
    return test_list(config_scope, 'all', caplog)

def test_list(config_scope, config_kind, caplog):

    token = ".".join(filter(None, (config_scope, config_kind)))

    if config_scope and config_kind is None:
        caplog.clear()
        res = run_and_test('config', 'list', token, success=False)
        assert ("Invalid " in caplog.text)
    else:
        res = run_and_test('config', 'list', token)
        assert (res.exit_code == 0)

    if config_scope and config_kind:
        caplog.clear()
        res = run_and_test('config', 'list', token+".test")
        assert ("no LABEL required for this command" in caplog.text)


def test_list_scope(config_kind, config_scope):
    for scope in pcvsrt.helpers.utils.storage_order():
        _ = run_and_test('config', 'list', ".".join([scope, config_kind]))


def test_list_wrong(caplog):
    caplog.clear()
    _ = run_and_test('config', 'list', 'error', success=False)
    assert ('Invalid KIND' in caplog.text)

    caplog.clear()
    _ = run_and_test('config', 'list', 'failure.compiler', success=False)
    assert ('Invalid SCOPE' in caplog.text)

    caplog.clear()
    _ = run_and_test('config', 'list', 'failure.compiler.extra.field', success=False)
    assert ('Invalid token' in caplog.text)


def test_show(config_scope, config_kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (config_scope, config_kind, 'test-show')))
        _ = run_and_test('config', 'create', token)
        _ = run_and_test('config', 'show', token)
        caplog.clear()
        _ = run_and_test('config', 'show', token + "-none", success=False)
        assert("configuration found at" in caplog.text)


def test_create(config_scope, config_kind, caplog):
    with isolated_fs():
        label = ".".join(filter(None, (config_scope, config_kind, 'creat')))
        _ = run_and_test('config', 'create', label)
        caplog.clear()
        _ = run_and_test('config', 'create', label, success=False)
        assert ("already exists!" in caplog.text)


def test_clone(config_scope, config_kind, caplog):
    with isolated_fs():
        basename = ".".join(filter(None, (config_scope, config_kind, 'base')))
        copyname = basename+"-copy"
        _ = run_and_test('config', 'create', basename)
        caplog.clear()
        _ = run_and_test('config', 'create', copyname, "--from", "base")
        caplog.clear()
        _ = run_and_test('config', 'create', copyname+"-2", "--from", "local.base")
        caplog.clear()
        
        _ = run_and_test('config', 'create', copyname+"none", "--from", "err", success=False)
        assert('Invalid ' in caplog.text)
        
        if config_kind == 'compiler':
            basename = basename.replace(config_kind, 'runtime')
        else:
            basename = basename.replace(config_kind, 'compiler')

        caplog.clear()
        _ = run_and_test('config', 'create', copyname + "-none", "--from",basename, success=False)
        assert('with the same KIND' in caplog.text)


def test_destroy(config_scope, config_kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (scoconfig_scopepe, config_kind, 'test')))
        
        # only invalid cases for creating a conf:
        if config_kind is None:
            _ = run_and_test('config', 'create', token, success=False)
            if config_scope is None:
                assert("You must specify" in caplog.text)
            else:
                assert ("Invalid KIND 'local'" in caplog.text)
            return

        caplog.clear()
        _ = run_and_test('config', 'create', token)
        caplog.clear()
        _ = run_and_test('config', 'destroy', token, success=False)
        caplog.clear()
        _ = run_and_test('config', 'destroy', '-f', token)
        caplog.clear()
        _ = run_and_test('config', 'destroy', '-f', token, success=False)
        assert("not found!" in caplog.text)
        

def test_import(config_scope, config_kind, caplog):
    with isolated_fs():
        fn = './tmp-file.yml'
        with open(fn, 'w') as f:
            f.write("""
            test:
                key: 'value'
            """)

        token = ".".join(filter(None, (config_scope, config_kind, 'test')))
        caplog.clear()
        res = run_and_test('config', 'import', token, success=False)
        assert ("Missing argument" in res.output)

        caplog.clear()
        _ = run_and_test('config', 'import', token, fn)
        caplog.clear()
        _ = run_and_test('config', 'import', token, fn, success=False)
        assert ("already created" in caplog.text)

        caplog.clear()
        _ = run_and_test('config', 'destroy', '-f', token)
        res = run_and_test('config', 'import', token, './non-existent-file', success=False)
        assert ("No such file or directory" in res.output)


def test_export(config_scope, config_kind, caplog):
    with isolated_fs():
        fn = "./tmp-file.yml"
        token = ".".join(filter(None, (config_scope, config_kind, 'test')))

        caplog.clear()
        _ = run_and_test('config', 'create', token)

        caplog.clear()
        res = run_and_test('config', 'export', token, success=False)
        assert ("Missing argument" in res.output)

        caplog.clear()
        _ = run_and_test('config', 'export', token, fn)
        assert (os.path.isfile(fn))
        
        caplog.clear()
        _ = run_and_test('config', 'export', token+"-err", fn, success=False)
        assert ("Failed to export" in caplog.text)



def test_edit(config_scope, config_kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (config_scope, config_kind, 'test')))
        caplog.clear()
        _ = run_and_test('config', 'create', token)
        _ = run_and_test('config', 'edit', '-e', 'cat', token)
        _ = run_and_test('config', 'edit', '-e', 'cat', token + "-none", success=False)
        assert('Cannot open this configuration: does not exist!' in caplog.text)
