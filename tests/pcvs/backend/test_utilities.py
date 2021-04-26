import os
from unittest.mock import patch

import pytest

from pcvs import NAME_BUILDIR
from pcvs.backend import utilities as tested


@pytest.fixture(params=[None, "/root"])
def prefix(request):
    return request.param

@pytest.fixture(params=["LABEL1/test_c1_N2", "D1/D2/D3/D4/test_c1_N2"])
def testname(request):
    return request.param

@pytest.fixture(params=[None, "test_c1_N2"])
def wrong_testname(request):
    return request.param

@patch('os.walk', return_value=[
            ('/', ('a', 'b'), ('README.md', 'LIST_OF_TESTS')),
            ('/a', ['c'], ["wrong_list_of_tests.sh"]),
            ('/a/c', [], ["list_of_tests.sh", "a.c"]),
            ('/b', [], ['list_of_tests.sh', "file.txt"]),
        ])
def test_locate_scriptpaths(prefix):
    result = tested.locate_scriptpaths(prefix)
    print(result)
    assert(len(result) == 2)
    for f in ["/b", "/a/c"]:
        assert(os.path.join(f, "list_of_tests.sh") in result)
