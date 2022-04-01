import json
import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from pcvs import NAME_BUILD_RESDIR, NAME_BUILDIR
from pcvs.backend import bank as tested
from pcvs.helpers import utils, git
from pcvs.helpers.system import MetaDict


@pytest.fixture
def mock_repo_fs():
    with CliRunner().isolated_filesystem():
        path = os.path.join(os.getcwd(), "fake_bank")
        os.makedirs(path)
        yield path
        
@pytest.fixture
def dummy_run():
    with CliRunner().isolated_filesystem():
        path = os.getcwd()
        build_path = os.path.join(path, ".pcvs-build")
        
        os.makedirs(os.path.join(build_path, "rawdata"))
        open(os.path.join(build_path, ".pcvs-isbuilddir"), 'w+').close()
        
        with open(os.path.join(build_path, "rawdata/pcvs_rawdat0000.json"), "w+") as fh:
            content = {
                "tests": [{
                    "id": {
                        "te_name": "test_main",
                        "label": "TBD",
                        "subtree": "tmp",
                        "fq_name": "tmp/test_main_c4_n4_N1_o4",
                        "comb": "TBD"
                    },
                    "exec": "mpirun --share-node --clean -c=4 -n=4 -N=1 /tmp/my_program ",
                    "result": {
                        "state": -1,
                        "time": 0.0,
                        "output": None
                    }, "data": {
                        "tags": "TBD",
                        "metrics": "TBD",
                        "artifacts": "TBD",
                        }}, 
                ]
            }
            json.dump(content, fh)
        
        with open(os.path.join(build_path, "conf.yml"), 'w') as fh:
            content = MetaDict()
            content.validation.dirs = {'LABEL_A': "DIR_A"}
            content.validation.author.name = "John Doe"
            content.validation.author.email = "johndoe@example.com"
            content.validation.datetime = datetime.now()
            content.validation.pf_hash = "profile_hash"
            YAML(typ='safe').dump(content.to_dict(), fh)

        yield path


@patch("pcvs.backend.bank.BANKS", {
    "default": "/random/path",
    "other": "/other/random/path"
})
def test_bank_init():
    obj = tested.Bank(token="default")
    obj2 = tested.Bank(path="/random/path")
    assert(obj.exists() and obj2.exists())
    assert(obj.name == obj2.name == "default")
    assert(obj.prefix == obj2.prefix == "/random/path")
    
    obj = tested.Bank(token="other@dummy-project")
    obj2 = tested.Bank(path="/other/random/path")
    assert(obj.exists() and obj2.exists())
    print(obj.prefix, obj2.prefix)
    assert(obj.prefix == obj2.prefix == "/other/random/path")
    assert(obj.name == obj2.name == "other")
    assert(obj.proj == "dummy-project")

    obj = tested.Bank(token="not-created")
    assert(not obj.exists())


def test_bank_connect(mock_repo_fs):
    # first test with a specific dir to create the Git repo
    obj = tested.Bank(path=mock_repo_fs)
    assert(not obj.exists())
    obj.connect_repository()
    assert(os.path.isfile(os.path.join(mock_repo_fs, "HEAD")))
    obj.disconnect_repository()

    # Then use the recursive research to let pygit2 detect the Git repo
    obj = tested.Bank(path=mock_repo_fs)
    assert(not obj.exists())
    obj.connect_repository()
    assert(obj.prefix == mock_repo_fs)  # pygit2 should detect the old repo
    assert(os.path.isfile(os.path.join(mock_repo_fs, "HEAD")))
    obj.connect_repository()  # ensure multiple connection are safe
    obj.disconnect_repository()

def test_save_run(mock_repo_fs, dummy_run, capsys):
    obj = tested.Bank(path=mock_repo_fs, token="dummy@original-tag")
    assert(not obj.exists())
    obj.connect_repository()
    prefix = utils.find_buildir_from_prefix(dummy_run)
    obj.save_from_buildir("override-tag", prefix)
    obj.save_from_buildir(None, prefix)
    assert(len(obj.list_projects()) == 2)
    assert(len(obj.list_series("override-tag")) == 1)
    assert(len(obj.list_series("original-tag")) == 1)
    obj.show()
    capture = capsys.readouterr()
    assert('original-tag: 1 distinct testsuite(s)' in capture.out)
    assert('override-tag: 1 distinct testsuite(s)' in capture.out)
    obj.disconnect_repository()
    
    repo = git.elect_handler(mock_repo_fs)
    repo.open()
    assert(len(list(repo.branches)) == 2)
    repo.set_head("original-tag/profile_hash")
    repo.set_head("override-tag/profile_hash")

