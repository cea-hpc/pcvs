from .cli_testing import run_and_test, isolated_fs
import pcvsrt
import os


def test_no_userdirs():
    with isolated_fs():
        _ = run_and_test('run')


def test_override(caplog):
    with isolated_fs():
        _ = run_and_test('run', '.')

        res = run_and_test('run', '.', success=False)
        assert(res.exit_code != 0)    
        assert ("Previous run artifacts found" in caplog.text)

        caplog.clear()
        _ = run_and_test('run', '.', '--override')
