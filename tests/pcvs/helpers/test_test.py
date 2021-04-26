import os
from unittest.mock import patch

import pytest
import pcvs
from pcvs.helpers import test as tested

from pcvs import PATH_INSTDIR, NAME_BUILDIR, NAME_SRCDIR
from pcvs.helpers import log
from pcvs.helpers import system
from unittest.mock import patch, Mock
from addict import Dict
from click.testing import CliRunner
import yaml
from pcvs.helpers import utils
from pcvs.helpers import exceptions

def legacy_yaml_file():
    assert(False)

log.init()

def load_yaml_file():
    assert(False)

@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_load_yaml_file():
    tested.load_yaml_file(os.path.join(PATH_INSTDIR, "schemes/criterion-scheme.yml"), 
        os.path.join(PATH_INSTDIR, "schemes"), 
        NAME_BUILDIR, 
        "schemes")

    # test invalid yml ?

    # tested.load_yaml_file(os.path.join(os.path.dirname(__file__), "appveyor.yml"), 
    #     os.path.join(PATH_INSTDIR, "schemes"), 
    #     NAME_BUILDIR, 
    #     "schemes")

@pytest.fixture
def isolated_yml_test():
    testyml = {
        "test_MPI_2INT":{
            "build":{
                "cflags": "-DSYMB=MPI_2INT -DTYPE1='int' -DTYPE='int'",
                "files": "'@SRCPATH@/constant.c'",
                "sources": {
                    "binary": "test_MPI_2INT"
                }
            },
            "group": "GRPSERIAL",
            "run":{
                "program": "test_MPI_2INT"
            },
            "tag": [
                "std_1",
                "constant"
            ]
        }
    }
    with CliRunner().isolated_filesystem():
        path = os.getcwd()
        testdir = "test-dir"
        os.makedirs(testdir)
        with open(os.path.join(path, testdir, "pcvs.yml"), "w") as fh:
            fh.write(yaml.safe_dump(testyml))
        yield path
    # utils.delete_folder(testdir)


@patch("pcvs.helpers.system.MetaConfig.root", system.MetaConfig({
    "__internal": {
        "cc_pm": "test_cc_pm"
    },
    "validation": {
        "output": "test_output",
        "dirs": {
            "keytestdir": "valuetestdir"
        }
    }
}))
@patch("pcvs.helpers.test.TEDescriptor")
@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_TestFile(tedesc, isolated_yml_test):
    def dummydesc(obj):
        pass
    tedesc.construct_tests = dummydesc
    l = log.IOManager(logfile = "out.log")
    testfile = tested.TestFile(os.path.join(isolated_yml_test, "test-dir/pcvs.yml"), 
        os.path.dirname(__file__), 
        label="keytestdir", 
        prefix=".")
    testfile.process()
    testfile.generate_debug_info()
    testfile.flush_sh_file()

def test_Test():
    test = tested.Test(name = "testname", 
        command = "testcommand", 
        nb_res = "testdim",
        te_name = "testte_name",
        subtree = "testsubtree",
        chdir = "testchdir",
        dep = "testdep",
        env = ["testenv"],
        matchers = {"matcher1": {"expr": "test"}},
        valscript = "testvalscript",)
    assert(test.name == "testname")
    assert(test.command == "testcommand")
    test.override_cmd("testnewcommand")
    assert(test.command == "testnewcommand")
    assert(test.get_dim() == "testdim")
    assert(test.been_executed() == False)
    assert(test.state == tested.Test.STATE_NOT_EXECUTED)
    test.executed()
    assert(test.been_executed() == True)
    testjson = test.to_json()
    assert(testjson["id"]["te_name"] == "testte_name")
    assert(testjson["id"]["subtree"] == "testsubtree")
    assert(testjson["id"]["full_name"] == "testname")
    assert(test.strstate == "OTHER")
    test.save_final_result()
    test.generate_script()

@patch("pcvs.helpers.system.MetaConfig.root", system.MetaConfig({
    "__internal": {
        "cc_pm": "test_cc_pm"
    },
    "validation": {
        "output": "test_output",
        "dirs": {
            "keytestdir": "valuetestdir"
        }
    },
    "group": {
        "GRPSERIAL": {}
    },
    "criterion": {}
}))
@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_TEDescriptor(isolated_yml_test):
    tested.TEDescriptor.init_system_wide("n_node")
    node = {
            "build":{
                "cflags": "-DSYMB=MPI_2INT -DTYPE1='int' -DTYPE='int'",
                "files": "'@SRCPATH@/constant.c'",
                "sources": {
                    "binary": "test_MPI_2INT"
                }
            },
            "group": "GRPSERIAL",
            "run": {
                "program": "test_MPI_2INT"
            },
            "tag": [
                "std_1",
                "constant"
            ]
        }
    tedesc = tested.TEDescriptor("foo", 
        node,
        "keytestdir", 
        "bar")
    # for i in tedesc.construct_tests():
    #     print(i)
    # raise Exception
    with pytest.raises(exceptions.TestException.TDFormatError):
        tested.TEDescriptor("foo", 
            "StrInsteadOfDict",
            "keytestdir", 
            "bar")

@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_replace_tokens():
    build = "/path/to/build"
    prefix = "dir1/dir2"
    src = "/path/to/src"

    assert(tested.replace_special_token(
                'build curdir is @BUILDPATH@',
                src, build, prefix
    ) == 'build curdir is /path/to/build/dir1/dir2')

    assert(tested.replace_special_token(
                'src curdir is @SRCPATH@',
                src, build, prefix
    ) == 'src curdir is /path/to/src/dir1/dir2')

    assert(tested.replace_special_token(
                'src rootdir is @ROOTPATH@',
                src, build, prefix
    ) == 'src rootdir is /path/to/src')

    assert(tested.replace_special_token(
                'build rootdir is @BROOTPATH@',
                src, build, prefix
    ) == 'build rootdir is /path/to/build')

    assert(tested.replace_special_token(
                'HOME is @HOME@',
                src, build, prefix
    ) == 'HOME is {}'.format("/home/user"))

    assert(tested.replace_special_token(
                'USER is @USER@',
                src, build, prefix
    ) == 'USER is {}'.format("superuser"))
