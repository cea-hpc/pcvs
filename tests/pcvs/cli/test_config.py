import os
from unittest.mock import Mock, patch

import pytest

import pcvs
from pcvs.cli import cli_config as tested

from .conftest import click_call


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
    res = click_call('config')
    assert('Usage:' in res.output)


def test_list_all(config_scope, caplog):
    return test_list(config_scope, 'all', caplog)

def test_list(config_scope, config_kind, caplog):

    token = ".".join(filter(None, (config_scope, config_kind)))

    if config_scope and config_kind is None:
        caplog.clear()
        res = click_call('config', 'list', token, success=False)
        assert ("Invalid " in caplog.text)
    else:
        res = click_call('config', 'list', token)
        assert (res.exit_code == 0)

    if config_scope and config_kind:
        caplog.clear()
        res = click_call('config', 'list', token+".test")
        assert ("no LABEL required for this command" in caplog.text)


def test_list_scope(config_kind, config_scope):
    for scope in pcvs.helpers.utils.storage_order():
        _ = click_call('config', 'list', ".".join([scope, config_kind]))


def test_list_wrong(caplog):
    caplog.clear()
    res = click_call('config', 'list', 'error')
    assert(res.exit_code != 0)
    assert ('Invalid KIND' in caplog.text)

    caplog.clear()
    res = click_call('config', 'list', 'failure.compiler')
    assert(res.exit_code != 0)
    assert ('Invalid SCOPE' in caplog.text)

    caplog.clear()
    res = click_call('config', 'list', 'failure.compiler.extra.field')
    assert(res.exit_code != 0)
    assert ('Invalid SCOPE' in caplog.text)

@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_show(mock_config, caplog):
    instance = mock_config.return_value
    instance.is_found.return_value = True

    res = click_call('config', 'show', 'dummy-config')
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.load_from_disk.assert_called_once_with()
    instance.display.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('config', 'show', 'dummy-config')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_create(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = False
    
    res = click_call('config', 'create', 'dummy-config')
    assert(res.exit_code == 0)
    instance.load_template.assert_called_once_with()
    instance.is_found.assert_called_once_with()
    #instance.clone.assert_called_once_with()
    instance.flush_to_disk.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = True
    res = click_call('config', 'create', 'dummy-config')
    assert(res.exit_code != 0)
    instance.load_template.assert_called_once_with()
    instance.is_found.assert_called_once_with()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_clone(mock_config):
    instance = mock_config.return_value
    res = click_call('config', 'create', 'compiler.dummy-config',
                     '-f', 'local.runtime.another')
    assert(res.exit_code != 0)
    instance.is_found.assert_not_called()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('config', 'create', 'compiler.dummy-config',
                     '-f', 'local.another')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_create_with_options(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = False
    res = click_call('config', 'create', '-i', 'local.compiler.random')
    assert(res.exit_code == 0)
    instance.open_editor.assert_called_once_with()


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_destroy(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = True
    res = click_call('config', 'destroy', '-f', "dummy-config")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.delete.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('config', 'destroy', '-f', "dummy-config")
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()
    instance.delete.assert_not_called()


def test_import(caplog):
    pass

def test_export(caplog):
    pass


@patch('pcvs.backend.config.ConfigurationBlock', autospec=True)
def test_edit(mock_config):
    instance = mock_config.return_value
    instance.is_found.return_value = True
    res = click_call('config', 'edit', "dummy-config")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.open_editor.assert_called_once_with(os.environ.get('EDITOR', None))
    
    instance.reset_mock()
    res = click_call('config', 'edit', "dummy-config", "-e", "editor")
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.open_editor.assert_called_once_with("editor")

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('config', 'edit', "dummy-config")
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()
    instance.open_editor.assert_not_called()