import pytest
from click.testing import CliRunner

from pcvs.backend import config
from pcvs.main import cli

runner = CliRunner()

def click_call(*cmd):
    return runner.invoke(cli, cmd)
    
def isolated_fs():
    return runner.isolated_filesystem()
