from click.testing import CliRunner
import pytest
from pcvs.main import cli
from pcvs.backend import config

runner = CliRunner()

def run_and_test(*cmd, success=True):
    res = runner.invoke(cli, cmd)
    return res

def isolated_fs():
    return runner.isolated_filesystem()
