import pytest
import os
from click.testing import CliRunner
from unittest.mock import patch
import addict
from datetime import datetime
import pcvs
from pcvs.backend import run as tested

@pytest.fixture
def mock_config():
    with CliRunner().isolated_filesystem():
        with patch.object(pcvs.helpers.system.MetaConfig, 'root', addict.Dict({
            'validation': {
                'output': os.getcwd(),
                'dirs': {'L1': os.getcwd()},
                'datetime': datetime.now(),
                'buildcache': os.path.join(os.getcwd(), "buildcache")
            }
        })):
            yield {
            
        }

@patch("pcvs.backend.session.Session", autospec=True)
def test_regular_run(mock_session, mock_config):
    pass
    #tested.process_main_workflow(mock_session)
    
    