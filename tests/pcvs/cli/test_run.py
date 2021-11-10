import os
from unittest.mock import patch

import pcvs
from pcvs.backend import run as tested

from .conftest import click_call, isolated_fs


@patch("pcvs.backend.session.lock_session_file", return_value={})
@patch("pcvs.backend.session.unlock_session_file", return_value={})
@patch("pcvs.backend.session.store_session_to_file", return_value={})
@patch("pcvs.backend.session.update_session_from_file", return_value={})
@patch("pcvs.backend.session.remove_session_from_file", return_value={})
def test_big_integation(rs, us, ss, unlock, lock):
    with isolated_fs():
        res = click_call('profile', 'create', 'local.default')
        assert(res.exit_code == 0)
        res = click_call('run')       
        assert(res.exit_code == 0)


@patch('pcvs.backend.session')
@patch('pcvs.backend.profile.Profile')
@patch('pcvs.backend.bank')
@patch('pcvs.helpers.system')
def override(mock_sys, mock_bank, mock_pf, mock_run, caplog):
    with isolated_fs():
        res = click_call('run', '.')
        assert(res.exit_code == 0)

        res = click_call('run', '.')
        assert(res.exit_code != 0)    
        assert ("Previous run artifacts found" in caplog.text)

        caplog.clear()
        _ = click_call('run', '.', '--override')
