from unittest.mock import Mock, patch

import pytest

import pcvs

from .conftest import click_call


@patch('pcvs.backend.profile.PROFILE_EXISTING', {
        'local': [('default', "/path/to/default.yml")],
        'user': [('user', "/path/to/user_override.yml")],
        'global': [('system-wide', "/path/to/system-wide.yml")]
        })
@patch('pcvs.backend.profile.Profile')
def test_check_profiles(mock_init):
    res = click_call('check', '--profiles')
    
    assert("Valid" in res.stdout)
    assert("Everything is OK!" in res.stdout)

@patch('pcvs.backend.config.CONFIG_EXISTING', {k: {
        'local': [('default', "/path/to/default.yml")],
        'user': [('user-{}'.format(k), "/path/to/user_override.yml")],
        'global': [('system-wide', "/path/to/system-wide.yml")]
        } for k in ['compiler', 'runtime', 'machine', 'criterion', 'group']
        })
@patch('pcvs.backend.config.ConfigurationBlock')
def test_check_configs(mock_init):
    res = click_call('check', '--configs')
    print(res.stdout)
    assert("Valid" in res.stdout)
    assert("Everything is OK!" in res.stdout)
    
def test_check_directory():
    res = click_call('check', '--directory', '.')