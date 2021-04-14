from .conftest import click_call, isolated_fs
from unittest.mock import patch
import pcvs
import os
from pcvs.backend import run as tested

def test_no_userdirs():
    with isolated_fs():
        _ = click_call('run')


@patch('pcvs.backend.run')
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
