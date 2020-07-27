from click.testing import CliRunner
from pcvsrt.scripts.cmd import cli
import pcvsrt
import os


def test_override(caplog):
    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(cli, ['run', '.'])
        assert (res.exit_code == 0)

        res = runner.invoke(cli, ['run', '.'])
        assert(res.exit_code != 0)    
        assert ("Previous run artifacts found" in caplog.text)

        res = runner.invoke(cli, ['run', '.', '--override'])
        assert (res.exit_code == 0)
