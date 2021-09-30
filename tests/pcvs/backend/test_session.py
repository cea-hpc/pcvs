import os
from datetime import datetime
from unittest import mock
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
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
    with CliRunner().isolated_filesystem():
        s = os.path.join(os.getcwd(), "session.yml")
        sl = os.path.join(os.getcwd(), ".session.yml.lck")
        with patch.object(tested, "PATH_SESSION", s) as mock_session:
            id = tested.store_session_to_file({"key": 'value'})
            with open(s, "r") as fh:
                data = YAML().load(fh)
                assert(len(data.keys()) == 2)
                assert('__metadata' in data)
                assert('next' in data['__metadata'])
                
                assert(id in data)
                assert('key' in data[id])
                assert('value' == data[id]['key'])
            
            tested.update_session_from_file(id, {
                "key": "new_value",
                "another_key": 'another_val'
                })
            with open(s, 'r') as fh:
                data = YAML().load(fh)
                assert(len(data.keys()) == 2)
                assert(id in data)
                assert('key' in data[id])
                assert('new_value' == data[id]['key'])
                assert('another_key' in data[id])
                assert('another_val' in data[id]['another_key'])
            
            sessions = tested.list_alive_sessions()
            assert(len(sessions) == 1)
            assert(id in sessions)
            
            tested.remove_session_from_file(id)
            with open(s, "r") as fh:
                data = YAML().load(fh)
                assert(id not in data)