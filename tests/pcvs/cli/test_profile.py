from unittest.mock import Mock, patch

import pytest

import pcvs

from .conftest import click_call


def test_cmd():
    res = click_call('profile')
    assert(res.exit_code == 0)
    assert('Usage:' in res.output)


@patch('pcvs.backend.profile.PROFILE_EXISTING', {
        'local': [('default', "/path/to/default.yml")],
        'user': [('user', "/path/to/user_override.yml")],
        'global': [('system-wide', "/path/to/system-wide.yml")]
        })
@patch('pcvs.backend.profile.init', return_value=None)
def test_list(mock_init):
    res = click_call('profile', 'list')
    assert(res.exit_code == 0)
    assert('default' in res.stdout)
    assert('user' in res.stdout)
    assert('system-wide' in res.stdout)

    res = click_call('profile', 'list', 'local')
    assert(res.exit_code == 0)
    assert('default' in res.stdout)
    assert('user' not in res.stdout)
    assert('system-wide' not in res.stdout)

    res = click_call('profile', 'list', 'global.system-wide')
    assert(res.exit_code == 0)
    assert('default' not in res.stdout)
    assert('user' not in res.stdout)
    assert('system-wide' in res.stdout)
    assert('no LABEL required' in res.stderr)


@patch('pcvs.backend.profile.Profile')
def test_show(mock_pf):
    instance = mock_pf.return_value
    instance.is_found.return_value = True
    res = click_call('profile', 'show', 'local.default')
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.load_from_disk.assert_called_with()
    instance.display.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('profile', 'show', 'local.default')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()
    instance.display.assert_not_called()


@patch('pcvs.backend.profile.Profile')
def test_create(mock_pf):
    instance = mock_pf.return_value
    instance.is_found.return_value = False
    res = click_call('profile', 'create', 'local.default')
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    #instance.clone.assert_called_once_with()
    instance.flush_to_disk.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = True
    res = click_call('profile', 'create', 'local.default')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()
    instance.flush_to_disk.assert_not_called()


@patch('pcvs.backend.profile.Profile')
def test_destroy(mock_pf):
    instance = mock_pf.return_value
    instance.is_found.return_value = True
    res = click_call('profile', 'destroy', '-f', 'local.default')
    assert(res.exit_code == 0)
    instance.is_found.assert_called_once_with()
    instance.delete.assert_called_once_with()

    instance.reset_mock()
    instance.is_found.return_value = False
    res = click_call('profile', 'destroy', '-f', 'local.default')
    assert(res.exit_code != 0)
    instance.is_found.assert_called_once_with()
    instance.delete.assert_not_called()
