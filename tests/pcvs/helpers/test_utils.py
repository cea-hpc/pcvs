import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pcvs.helpers import utils as tested
from pcvs.helpers.exceptions import CommonException, RunException
from pcvs.helpers.system import MetaDict


@pytest.mark.parametrize("token", ["test1", "test/test1"])
def test_token_extraction_1(token):
    assert(tested.extract_infos_from_token(token) == (None, None, token))
    assert(tested.extract_infos_from_token(token, single="right") == (None, None, token))
    assert(tested.extract_infos_from_token(token, single="center") == (None, token, None))
    assert(tested.extract_infos_from_token(token, single="left") == (token, None, None))

@pytest.mark.parametrize("token", ["runtime.test1", "compiler.test/test1"])
def test_token_extraction_2(token):
    split = token.split(".")
    assert(tested.extract_infos_from_token(token) == (None, split[0], split[1]))
    assert(tested.extract_infos_from_token(token, pair="right") == (None, split[0], split[1]))
    assert(tested.extract_infos_from_token(token, pair="span") == (split[0], None, split[1]))
    assert(tested.extract_infos_from_token(token, pair="left") == (split[0], split[1], None))

@pytest.mark.parametrize("token", ["local.runtime.test1",
                                   "global.compiler.test/test1"
                                   "global.comppiler.this.is.a.test"])
def test_token_extraction_3(token):
    split = token.split(".")
    assert(tested.extract_infos_from_token(token) == (split[0], split[1], ".".join(split[2:])))


def test_path_cleaner():
    with CliRunner().isolated_filesystem():
        os.makedirs("./A/B/C/D")
        open("./A/B/C/D/file.txt", "w").close()

        tested.create_or_clean_path("A/B/C/D/file.txt")
        assert(not os.path.exists("A/B/C/D/file.txt"))
        tested.create_or_clean_path("A/B")
        assert(os.path.isdir("A/B"))
        assert(len(os.listdir("A/B")) == 0)


@pytest.mark.parametrize("wd_dir", ["/home", "/", "/tmp", "./dummy-dir"])
def test_cwd_manager(wd_dir):

    with CliRunner().isolated_filesystem():
        ref_path = os.path.abspath(wd_dir)
        with tested.cwd(wd_dir):
            assert(os.getcwd() == ref_path)

@patch("pcvs.helpers.system.MetaConfig.root", MetaDict({
    "validation": {
        'output': "/prefix_build",
        "dirs": {'LABEL1': '/prefix1', 'LABEL2': "/prefix2"}
}}))

@pytest.mark.parametrize("program", ["ls", "/bin/sh"])
def test_check_program(program):
    class Success(Exception): pass
    def succ_func(msg):
        assert("'{}' found at '".format(os.path.basename(program)) in msg)
        raise Success()

    tested.check_valid_program(None)
    with pytest.raises(Success):
        tested.check_valid_program(program, succ=succ_func)
    tested.check_valid_program(program)

@pytest.mark.parametrize("program", ["invalid-program", "./setup.py"])
def test_check_wrong_program(program):
    class Failure(Exception): pass
    def fail_func(msg):
        assert(msg == "{} not found or not an executable".format(program))
        raise Failure()

    with pytest.raises(Failure):
        tested.check_valid_program(program, fail=fail_func)
    with pytest.raises(RunException.ProgramError):
        tested.check_valid_program(program)

    tested.check_valid_program(program, raise_if_fail=False)
    
