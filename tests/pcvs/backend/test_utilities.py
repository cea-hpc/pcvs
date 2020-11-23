from pcvs.backend import utilities as tested
from pcvs import BUILD_NAMEDIR
import pytest
import os

@pytest.fixture(params=[None, "/root"])
def prefix(request):
    return request.param

@pytest.fixture(params=["LABEL1/test_c1_N2", "D1/D2/D3/D4/test_c1_N2"])
def testname(request):
    return request.param

@pytest.fixture(params=[None, "test_c1_N2"])
def wrong_testname(request):
    return request.param

def test_locate_scriptpaths(monkeypatch, prefix):
    def mock_filetree(path):
        return [
            ('/', ('a', 'b'), ('README.md', 'LIST_OF_TESTS')),
            ('/a', ['c'], ["wrong_list_of_tests.sh"]),
            ('/a/c', [], ["list_of_tests.sh", "a.c"]),
            ('/b', [], ['list_of_tests.sh', "file.txt"]),
        ]
    monkeypatch.setattr(os, 'walk', mock_filetree)
    
    result = tested.locate_scriptpaths(prefix)
    print(result)
    assert(len(result) == 2)
    for f in ["/b", "/a/c"]:
        assert(os.path.join(f, "list_of_tests.sh") in result)


def test_compute_scriptpath(testname, prefix):
    result = tested.compute_scriptpath_from_testname(testname, prefix)
    if prefix is None:
        prefix = os.path.join(os.getcwd(), BUILD_NAMEDIR, "test_suite")
    assert(result == os.path.join(prefix, os.path.dirname(testname), "list_of_tests.sh" ))
