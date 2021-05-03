from unittest.mock import patch

from pcvs.helpers import log, system
from pcvs.testing import test as tested


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
def test_Test():
    test = tested.Test(name = "testname", 
        label="label",
        tags=None,
        artifacts={},
        comb_dict=None,
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
    #assert(test.strstate == "OTHER")
    test.save_final_result()
    test.generate_script("output_file.sh")
