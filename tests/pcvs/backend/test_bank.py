import os

import pytest

import pcvs
from pcvs.backend import bank as tested
from pcvs.helpers import git
from pcvs.helpers import utils

from ..conftest import dummy_run_fs
from ..conftest import isolated_fs


@pytest.fixture
def dummy_run():
    with dummy_run_fs() as path:
        yield path


@pytest.fixture
def mock_repo_fs():
    with isolated_fs() as tmp:
        path = os.path.join(tmp, "fake_bank")
        os.makedirs(path)
        yield path


def test_bank_connect(mock_repo_fs):  # pylint: disable=redefined-outer-name
    # first test with a specific dir to create the Git repo
    pcvs.io.init()
    obj = tested.Bank(mock_repo_fs)
    obj.connect()
    assert os.path.isfile(os.path.join(mock_repo_fs, "HEAD"))
    obj.disconnect()

    # Then use the recursive research to let pygit2 detect the Git repo
    obj = tested.Bank(mock_repo_fs)
    obj.connect()
    assert obj.prefix == mock_repo_fs  # pygit2 should detect the old repo
    assert os.path.isfile(os.path.join(mock_repo_fs, "HEAD"))
    obj.connect()  # ensure multiple connection are safe
    obj.disconnect()


def test_save_run(mock_repo_fs, dummy_run, capsys):  # pylint: disable=redefined-outer-name
    pcvs.io.init()
    obj = tested.Bank(f"original-tag@{mock_repo_fs}")
    obj.connect()
    prefix = utils.find_buildir_from_prefix(dummy_run)
    obj.save_from_buildir("override-tag", prefix)
    assert obj.get_count() == 1

    obj.save_from_buildir(None, prefix)
    assert obj.get_count() == 2

    assert len(obj.list_series("override-tag")) == 1
    assert len(obj.list_series("original-tag")) == 1
    obj.show()
    capture = capsys.readouterr()
    assert "original-tag: 1 distinct testsuite(s)" in capture.out
    assert "override-tag: 1 distinct testsuite(s)" in capture.out
    obj.disconnect()

    repo = git.elect_handler(mock_repo_fs)
    repo.open()
    assert len(list(repo.branches())) == 3


def test_diff_tree(mock_repo_fs):  # pylint: disable=redefined-outer-name
    pcvs.io.init()
    g = git.elect_handler(mock_repo_fs)
    g.open()
    g.set_identity("Test", "test@test.com", "Test", "test@test.com")

    # First commit: add a single file
    root = g.insert_tree("file1.txt", "content1")
    c1 = g.do_commit(root, "first commit", orphan=True)
    g.set_branch(git.Branch(g, "master"), c1)

    # Second commit: add another file, modify existing one
    root = g.insert_tree("file1.txt", "content1_modified")
    root = g.insert_tree("file2.txt", "content2", root)
    c2 = g.do_commit(root, "second commit", parent=git.Branch(g, "master"))

    # diff between c1 and c2 returns content of changed files from dst_rev
    contents = g.diff_tree(src_rev=c1, dst_rev=c2)
    assert "content1_modified" in contents
    assert "content2" in contents
    assert len(contents) == 2

    # filter by prefix
    contents_filtered = g.diff_tree(prefix="file1", src_rev=c1, dst_rev=c2)
    assert len(contents_filtered) == 1
    assert contents_filtered[0] == "content1_modified"

    # diff with no changes
    contents_same = g.diff_tree(src_rev=c2, dst_rev=c2)
    assert len(contents_same) == 0

    # diff using branch as reference (master points to c2 after do_commit,
    # so we diff c1 vs master which should show the same changes)
    contents_branch = g.diff_tree(src_rev=c1, dst_rev=git.Branch(g, "master"))
    assert "content1_modified" in contents_branch
    assert "content2" in contents_branch

    g.close()
