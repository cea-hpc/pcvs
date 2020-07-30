from click.testing import CliRunner
import pytest
from pcvsrt.cli.cmd import cli

runner = CliRunner()

def run_and_test(*cmd, success=True):
    res = runner.invoke(cli, cmd)
    if success:
        assert (res.exit_code == 0)
    else:
        assert (res.exit_code != 0)
    return res

def isolated_fs():
    return runner.isolated_filesystem()