import os
from unittest.mock import patch

import pytest

from pcvs.helpers import test as tested

from pcvs import PATH_INSTDIR, NAME_BUILDIR, NAME_SRCDIR
from pcvs.helpers import log
def legacy_yaml_file():
    assert(False)

log.init()

def load_yaml_file():
    assert(False)

@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_load_yaml_file():
    log.manager.print(NAME_BUILDIR)
    tested.load_yaml_file(os.path.join(PATH_INSTDIR, "schemes/criterion-scheme.yml"), 
        os.path.join(PATH_INSTDIR, "schemes"), 
        NAME_BUILDIR, 
        "schemes")

    # test invalid yml ?

    # tested.load_yaml_file(os.path.join(os.path.dirname(__file__), "appveyor.yml"), 
    #     os.path.join(PATH_INSTDIR, "schemes"), 
    #     NAME_BUILDIR, 
    #     "schemes")

def test_TestFile():
    pass
    # testfile = tested.TestFile(os.path.join(PATH_INSTDIR, "schemes/criterion-scheme.yml"), os.path.dirname(__file__), label="test", prefix="schemes")
    # testfile.process()

def test_Test():
    test = tested.Test(name = "testname", 
        command = "testcommand", 
        nb_res = "testdim",
        te_name = "testte_name",
        subtree = "testsubtree",
        chdir = "testchdir",
        dep = "testdep")
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
