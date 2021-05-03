from click.testing import CliRunner

from pcvs.main import cli

runner = CliRunner(mix_stderr=False)

def click_call(*cmd):
    return runner.invoke(cli, ["--no-color", *cmd], catch_exceptions=False)
    
def isolated_fs():
    return runner.isolated_filesystem()
