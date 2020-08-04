import pcvsrt
import pytest
import os
from .cli_testing import run_and_test, isolated_fs

def test_cmd():
    res = run_and_test('config')
    assert('Usage:' in res.output)

@pytest.mark.parametrize(
    'kind',
    [None, 'all', 'compiler', 'runtime', 'machine', 'criterion', 'group'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_list(scope, kind, caplog):

    token = ".".join(filter(None, (scope, kind)))

    if scope and kind is None:
        caplog.clear()
        res = run_and_test('config', 'list', token, success=False)
        assert ("Invalid " in caplog.text)
    else:
        res = run_and_test('config', 'list', token)
        assert (res.exit_code == 0)

    if scope and kind:
        caplog.clear()
        res = run_and_test('config', 'list', token+".test")
        assert ("no LABEL required for this command" in caplog.text)


@pytest.mark.parametrize(
    'kind',
    ['all', 'compiler', 'runtime', 'machine', 'criterion', 'group'])
def test_list_scope(kind):
    for scope in pcvsrt.globals.storage_order():
        _ = run_and_test('config', 'list', ".".join([scope, kind]))


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


@pytest.mark.parametrize( 
    'kind',
    ['compiler', 'runtime', 'machine', 'criterion', 'group'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_show(scope, kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (scope, kind, 'test-show')))
        _ = run_and_test('config', 'create', token)
        _ = run_and_test('config', 'show', token)
        caplog.clear()
        _ = run_and_test('config', 'show', token + "-none", success=False)
        assert("configuration found at" in caplog.text)


@pytest.mark.parametrize(
    'kind',
    ['compiler', 'runtime', 'machine', 'criterion', 'group'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_create(scope, kind, caplog):
    with isolated_fs():
        label = ".".join(filter(None, (scope, kind, 'creat')))
        _ = run_and_test('config', 'create', label)
        caplog.clear()
        _ = run_and_test('config', 'create', label, success=False)
        assert ("already exists!" in caplog.text)


@pytest.mark.parametrize(
    'kind',
    ['compiler', 'runtime', 'machine', 'criterion', 'group'])
@pytest.mark.parametrize('scope', ['local'])
def test_clone(scope, kind, caplog):
    with isolated_fs():
        basename = ".".join(filter(None, (scope, kind, 'base')))
        copyname = basename+"-copy"
        _ = run_and_test('config', 'create', basename)
        caplog.clear()
        _ = run_and_test('config', 'create', copyname, "--from", "base")
        caplog.clear()
        _ = run_and_test('config', 'create', copyname+"-2", "--from", "local.base")
        caplog.clear()
        
        _ = run_and_test('config', 'create', copyname+"none", "--from", "err", success=False)
        assert('Invalid ' in caplog.text)
        
        if kind == 'compiler':
            basename = basename.replace(kind, 'runtime')
        else:
            basename = basename.replace(kind, 'compiler')

        caplog.clear()
        _ = run_and_test('config', 'create', copyname + "-none", "--from",basename, success=False)
        assert('with the same KIND' in caplog.text)


@pytest.mark.parametrize('kind', [None, 'compiler', 'runtime', 'group', 'machine', 'criterion'])
@pytest.mark.parametrize('scope', [None, 'local']
)
def test_destroy(scope, kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (scope, kind, 'test')))
        
        # only invalid cases for creating a conf:
        if kind is None:
            _ = run_and_test('config', 'create', token, success=False)
            if scope is None:
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
        

@pytest.mark.parametrize('kind', ['compiler', 'runtime', 'group', 'machine', 'criterion'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_import(scope, kind, caplog):
    with isolated_fs():
        fn = './tmp-file.yml'
        with open(fn, 'w') as f:
            f.write("""
            test:
                key: 'value'
            """)

        token = ".".join(filter(None, (scope, kind, 'test')))
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


@pytest.mark.parametrize( 'kind', ['compiler', 'runtime', 'group', 'machine', 'criterion'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_export(scope, kind, caplog):
    with isolated_fs():
        fn = "./tmp-file.yml"
        token = ".".join(filter(None, (scope, kind, 'test')))

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



@pytest.mark.parametrize( 'kind', ['compiler', 'runtime', 'group', 'machine', 'criterion'])
@pytest.mark.parametrize('scope', [None, 'local'])
def test_edit(scope, kind, caplog):
    with isolated_fs():
        token = ".".join(filter(None, (scope, kind, 'test')))
        caplog.clear()
        _ = run_and_test('config', 'create', token)
        _ = run_and_test('config', 'edit', '-e', 'cat', token)
        _ = run_and_test('config', 'edit', '-e', 'cat', token + "-none", success=False)
        assert('Cannot open this configuration: does not exist!' in caplog.text)
