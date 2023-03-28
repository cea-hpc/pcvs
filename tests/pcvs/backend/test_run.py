import os
import stat
from datetime import datetime
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import pcvs
from pcvs.backend import run as tested
from pcvs.helpers.exceptions import ValidationException
from pcvs.helpers.system import MetaConfig, MetaDict
from pcvs.plugins import Collection

good_content = """#!/bin/sh
echo 'test_node:'
echo '  build:'
echo '    sources:'
echo '      binary: "a.out"'
"""

bad_output = """#!/bin/sh
echo "test_node:"
echo "  unknown_node: 'test'"
"""

bad_script = """#!/bin/sh
echo "failure"
exit 42
"""

def help_create_setup_file(path, s):
    os.makedirs(os.path.dirname(path))
    with open(path, 'w') as fh:
        fh.write(s)
    os.chmod(path, stat.S_IRUSR | stat.S_IXUSR)


@pytest.fixture
def mock_config():
    with CliRunner().isolated_filesystem():
        with patch.object(pcvs.helpers.system.MetaConfig, 'root', MetaConfig({
            'validation': {
                'output': os.getcwd(),
                'dirs': {'L1': os.getcwd()},
                'datetime': datetime.now(),
                'buildcache': os.path.join(os.getcwd(), "buildcache")
            },
            '_MetaConfig__internal_config': {
                'pColl': Collection()
            }
        })):
            yield {}

#@patch("pcvs.backend.session.Session", autospec=True)
#def test_regular_run(mock_session, mock_config):
    #tested.process_main_workflow(mock_session)
    #pass
def test_process_setup_scripts(mock_config):
    d = os.path.join(MetaConfig.root.validation.dirs['L1'], "subtree")
    f = os.path.join(d, "pcvs.setup")
    help_create_setup_file(f, good_content)
    pcvs.io.init()
    with patch("pcvs.testing.tedesc.TEDescriptor") as mock_ted:
        err = tested.process_dyn_setup_scripts([("L1", "subtree", "pcvs.setup")])
        assert(len(err) == 0)
    
def test_process_bad_setup_script(mock_config):
    d = os.path.join(MetaConfig.root.validation.dirs['L1'], "subtree")
    f = os.path.join(d, "pcvs.setup")
    help_create_setup_file(f, bad_script)
    pcvs.io.init()
    err = tested.process_dyn_setup_scripts([("L1", "subtree", "pcvs.setup")])
    assert(len(err) == 1)
    assert(err[0][0] == f)
    assert("exit 42" in err[0][1])
    

def test_process_wrong_setup_script(mock_config):
    d = os.path.join(MetaConfig.root.validation.dirs['L1'], "subtree")
    f = os.path.join(d, "pcvs.setup")
    help_create_setup_file(f, bad_output)
    pcvs.io.init()
    with pytest.raises(ValidationException.FormatError) as e:
        tested.process_dyn_setup_scripts([("L1", "subtree", "pcvs.setup")])