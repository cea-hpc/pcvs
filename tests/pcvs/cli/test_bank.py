import os
from pathlib import Path

from ..conftest import click_call
from ..conftest import dummy_bank_fs
from ..conftest import dummy_run_fs


def test_init():
    """Test bank create."""
    with dummy_bank_fs() as tmp:
        res = click_call("bank", "init", "test1", "test")
        assert res.exit_code == 0
        assert Path("test").is_dir()
        res = click_call("bank", "init", "test2", "test")
        assert res.exit_code != 0

        test2_path = Path(tmp).joinpath("testdir").joinpath("test3")
        test2_path.parent.mkdir(parents=True)
        res = click_call("bank", "init", "test3", "testdir/test3")
        assert res.exit_code == 0
        assert test2_path.is_dir()

        test3_path = Path(tmp).joinpath("testdir").joinpath("test4")
        res = click_call("bank", "init", "test1", "testdir/test4")
        assert res.exit_code != 0
        assert not test3_path.is_dir()


def test_destroy():
    """Test bank destroy."""
    with dummy_bank_fs():
        res = click_call("bank", "init", "test", "testdir")
        res = click_call("bank", "destroy", "-f", "test")
        assert res.exit_code == 0
        res = click_call("bank", "destroy", "test")
        assert res.exit_code != 0
        res = click_call("bank", "destroy", "testdir")
        assert res.exit_code != 0


def test_list():
    """Test bank list."""
    with dummy_bank_fs():
        res = click_call("bank", "init", "test", "test")
        res = click_call("bank", "list")
        assert res.exit_code == 0
        assert res.stdout.find("test:") != -1


def test_show():
    """Test bank show."""
    with dummy_bank_fs():
        res = click_call("bank", "init", "test", "test")
        res = click_call("bank", "show", "test")
        assert res.exit_code == 0
        assert res.stdout.find("Projects contained in bank") != -1


def test_save():
    """Test bank save."""
    with dummy_run_fs() as tmp:
        res = click_call("bank", "init", "test")
        assert res.exit_code == 0
        res = click_call("bank", "save", "test", os.path.join(tmp, ".pcvs-build"))
        assert res.exit_code == 0


def test_load():
    """Test bank load."""
    with dummy_run_fs() as tmp:
        res = click_call("bank", "init", "test")
        assert res.exit_code == 0
        res = click_call("bank", "save", "test", os.path.join(tmp, ".pcvs-build"))
        assert res.exit_code == 0
        res = click_call("bank", "load", "test")
        assert res.exit_code == 0
