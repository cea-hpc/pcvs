import os
from datetime import datetime
from unittest import mock
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

import pcvs
from pcvs.backend import session as tested


def dummy_main_function(arg_a, arg_b):
    assert(arg_a == "argument_a")
    assert(arg_b == ["argument_b"])

@pytest.fixture
def mock_home_config():
    with CliRunner().isolated_filesystem():
        mock.patch.object(pcvs, 'PATH_SESSION', os.path.join(os.getcwd(), "session.yml")
        )


def test_session_init():
    date = datetime.now()
    obj = tested.Session(date)
    assert(str(obj.state) == "WAITING")
    assert(obj.property('started') == date)


def test_session_file():
    return
    with CliRunner().isolated_filesystem():
        with mock.patch('pcvs.backend.session.PATH_SESSION') as mock_pcvs:
            mock_pcvs.PATH_SESSION = os.path.join(os.getcwd(), '.pcvs/session.yml')
            print(pcvs.PATH_HOMEDIR)
            test_dict = {
                    'state': tested.Session.State.COMPLETED,
                    'started': datetime.now()
            }
            
            assert(pcvs.PATH_SESSION == os.path.join(os.getcwd(), '.pcvs', 'session.yml'))
            tested.store_session_to_file(test_dict)
            #assert(os.path.isfile(os.path.join(os.getcwd(), 'session.yml.lck')))
            
            with open(pcvs.PATH_SESSION, 'r') as fh:
                content = yaml.safe_load(fh)
                tested_content = tested.list_alive_sessions()
                assert(content == tested_content)
                assert(len(content.keys()) == 1)
                assert(content['0'] == test_dict)
            
            tested.update_session_from_file(0, {'ended': datetime.now()})
            
            with open(pcvs.PATH_SESSION, 'r') as fh:
                content = yaml.safe_load(fh)
                assert(content.keys() == 1)
                assert('ended' in content['0'])

            tested.remove_session_from_file(0)
            with open(pcvs.PATH_SESSION, 'r') as fh:
                assert(yaml.safe_load(fh) == None)