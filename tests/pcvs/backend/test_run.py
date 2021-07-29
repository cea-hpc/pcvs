import os
from datetime import datetime
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import pcvs
from pcvs.backend import run as tested
from pcvs.helpers.system import MetaDict


@pytest.fixture
def mock_config():
    with CliRunner().isolated_filesystem():
        with patch.object(pcvs.helpers.system.MetaConfig, 'root', MetaDict({
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
    
    