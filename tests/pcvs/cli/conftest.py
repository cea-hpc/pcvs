from click.testing import CliRunner
import pytest
from pcvs.main import cli
from pcvs.backend import config

runner = CliRunner()

def click_call(*cmd):
    return runner.invoke(cli, cmd)
    
def isolated_fs():
    return runner.isolated_filesystem()
