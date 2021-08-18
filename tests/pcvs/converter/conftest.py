from click.testing import CliRunner

from pcvs.converter.yaml_converter import main

runner = CliRunner(mix_stderr=False)


def click_call(*cmd):
    return runner.invoke(main, ["--no-color", *cmd], catch_exceptions=False)


def isolated_fs():
    return runner.isolated_filesystem()
