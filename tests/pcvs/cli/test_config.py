import os
import pcvs
import pytest
import os
from .conftest import run_and_test
from pcvs.cli import cli_config as tested
from unittest.mock import patch, Mock


@pytest.fixture(params=pcvs.backend.config.CONFIG_BLOCKS)
def config_kind(request):
    return request.param

@pytest.fixture(params=pcvs.helpers.utils.storage_order())
def config_scope(request):
    return request.param


@patch('pcvs.backend.config.CONFIG_EXISTING', {k: {
        'local': [('default', "/path/to/default.yml")],
        'user': [('user-{}'.format(k), "/path/to/user_override.yml")],
        'global': [('system-wide', "/path/to/system-wide.yml")]
        } for k in ['compiler', 'runtime', 'machine', 'criterion', 'group']
        })
@patch('pcvs.backend.config.init')
def test_completion(mock_init):    
    assert(set(tested.compl_list_token(None, None, "local.")) == {
        "local.compiler.default", "local.runtime.default", "local.machine.default",
        "local.group.default", "local.criterion.default"})
    assert(set(tested.compl_list_token(None, None, "user-com")) == {"user.compiler.user-compiler"})
    assert(set(tested.compl_list_token(None, None, "runtime.sys")) == {"global.runtime.system-wide"})


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
    for scope in pcvs.helpers.utils.storage_order():
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
    assert ('Invalid SCOPE' in caplog.text)

@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_show(mock_config, caplog):
    instance = mock_config.return_value
    instance.is_found.return_value = True

    res = run_and_test('config', 'show', 'dummy-config')
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once()
    instance.load_from_disk.assert_called_once()
    instance.display.assert_called_once()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = run_and_test('config', 'show', 'dummy-config')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_create(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = False
    
    res = run_and_test('config', 'create', 'dummy-config')
    assert(res.exit_code == 0)
    instance.load_template.assert_called_once()
    instance.is_found.assert_called_once()
    instance.clone.assert_called_once()
    instance.flush_to_disk.assert_called_once()

    instance.reset_mock()
    instance.is_found.return_value = True
    res = run_and_test('config', 'create', 'dummy-config')
    assert(res.exit_code != 0)
    instance.load_template.assert_called_once()
    instance.is_found.assert_called_once()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_create_with_options(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = False
    res = run_and_test('config', 'create', '-i', 'local.compiler.random')
    assert(res.exit_code == 0)
    instance.open_editor.assert_called_once()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_destroy(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = True
    res = run_and_test('config', 'destroy', '-f', "dummy-config")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once()
    instance.delete.assert_called_once()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = run_and_test('config', 'destroy', '-f', "dummy-config")
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once()
    instance.delete.assert_not_called()


def test_import(caplog):
    pass

def test_export(caplog):
    pass


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_edit(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = True
    res = run_and_test('config', 'edit', "dummy-config")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once()
    instance.open_editor.assert_called_once_with(os.environ.get('EDITOR', None))
    
    instance.reset_mock()
    res = run_and_test('config', 'edit', "dummy-config", "-e", "editor")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once()
    instance.open_editor.assert_called_once_with("editor")

    instance.reset_mock()
    instance.is_found.return_value = False
    res = run_and_test('config', 'edit', "dummy-config")
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once()
    instance.open_editor.assert_not_called()