import os
from unittest.mock import patch

import pytest

import pcvs
from pcvs.helpers import criterion, exceptions, pm, system
from pcvs.plugins import Collection
from pcvs.helpers.criterion import Criterion
from pcvs.helpers.system import MetaDict
from pcvs.testing import tedesc as tested


@patch('pcvs.helpers.system.MetaConfig.root', MetaDict({
            'compiler': {
                'commands': {
                    'cc': 'CC',
                    'cxx': 'CXX',
                    'fc': 'FC',
                    'f77': 'F77',
                    'f90': 'F90',
                    'f95': 'F95',
                    'f03': 'F03',
                    'f08': 'F08'
                }
        }}))
def test_lang_detection():
    assert(tested.detect_source_lang(["/path/to/nothing.valid"]) == 'cc')
    assert(tested.detect_source_lang(["/path/to/a.c"]) == 'cc')
    assert(tested.detect_source_lang(["/path/to/a.h"]) == 'cc')
    assert(tested.detect_source_lang(["/path/to/a.cc"]) == 'cxx')
    assert(tested.detect_source_lang(["/path/to/a.cpp"]) == 'cxx')
    assert(tested.detect_source_lang(["/path/to/a.f"]) == 'fc')
    assert(tested.detect_source_lang(["/path/to/a.f77"]) == 'f77')
    assert(tested.detect_source_lang(["/path/to/a.f90"]) == 'f90')
    assert(tested.detect_source_lang(["/path/to/a.f95"]) == 'f95')
    assert(tested.detect_source_lang(["/path/to/a.F03"]) == 'f03')
    assert(tested.detect_source_lang(["/path/to/a.f08"]) == 'f08')
    
    assert(tested.detect_source_lang(["/path/to/a.c",
                                      "/path/to/b.cpp"]) == 'cxx')
    
    assert(tested.detect_source_lang(["/path/to/a.f77",
                                      "/path/to/a.f08"]) == 'f08')


@patch('pcvs.helpers.pm.identify')
def test_handle_job_deps(mock_id):
    #mock_pmlister.return_value = 
    assert(tested.build_job_deps({'depends_on': ['a', 'b', 'c']
    }, "label", "prefix") == ["label/prefix/a", "label/prefix/b", "label/prefix/c"])

    assert(tested.build_job_deps({'depends_on': ['/a', '/b', '/c']
    }, "label", "prefix") == ["/a", "/b", "/c"])

    mock_id.return_value = ["spack..p1", "spack..p1c2", "spack..p1p3%c4"]
    assert(len(tested.build_pm_deps({'package_manager': {
        'spack': ['p1', 'p1@c2', 'p1 p3 %c4']
    }})) == 3)

    assert(len(tested.build_job_deps({}, "", "")) == 0)


@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
@patch("pcvs.helpers.system.MetaConfig.root", system.MetaConfig({
    "_MetaConfig__internal_config": {
        "cc_pm": pm.SpackManager("this_is_a_test"),
        'pColl': Collection(),
    },
    "validation": {
        "output": "test_output",
        "dirs": {
            "label": "/this/directory"
        }
    },
    "group": {
        "GRPSERIAL": {}
    },
    "criterion": {
        "n_mpi": {"option": "-n ", "numeric": True, "values": [1, 2, 3, 4]}}
}))
def test_tedesc_regular():
    criterion.initialize_from_system()
    tested.TEDescriptor.init_system_wide("n_node")
    node = {
            "build":{
                "cflags": "-DSYMB=MPI_2INT -DTYPE1='int' -DTYPE='int'",
                "files": "@SRCPATH@/constant.c",
                "sources": {
                    "binary": "test_MPI_2INT"
                }
            },
            "group": "GRPSERIAL",
            "run": {
                "program": "test_MPI_2INT",
                "iterate": {
                    "n_mpi": {
                        "values": [1, 2, 3, 4]
                    }
                },
                    
            },
            "tag": [
                "std_1",
                "constant"
            ]
        }
    tedesc = tested.TEDescriptor("te_name",
        node,
        "label", 
        "subtree")
    
    assert(tedesc.name == "te_name")
    for i in tedesc.construct_tests():
        print(i.command)

    
    with pytest.raises(exceptions.TestException.TDFormatError):
        tested.TEDescriptor("te_name", 
            "bad_type",
            "label", 
            "subtree")
        
        tested.TEDescriptor("te_name", 
            {"build": {"unknown_key": 2}},
            "label", 
            "subtree")

@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
@patch("pcvs.helpers.system.MetaConfig.root", system.MetaConfig({
    "_MetaConfig__internal_config": {
        "cc_pm": pm.SpackManager("this_is_a_test"),
    },
    "validation": {
        "output": "test_output",
        "dirs": {
            "label": "/this/directory"
        }
    },
    "group": {
        "GRPSERIAL": {}
    },
    "criterion": {"n_mpi": {"option": "-n ", "numeric": True, "values": [1, 2, 3, 4]}}
}))
def test_tedesc_compilation():
    criterion.initialize_from_system()
    tested.TEDescriptor.init_system_wide("n_node")
    dict_of_tests = [
        {"build": {
            "files": ["a.c", "b.c"],
            "sources": {
                "binary": "a.out"
            }
        }},
        {"build": {
            "files": "@SRCPATH@/Makefile",
            "make": {
                "target": "all"
            }
        }},
        {"build": {
            "files": ["@BUIDLPATH@/configure"],
            "autotools": {
                "autogen": True,
            }
        }},
        {"build": {
            "files": "@SRCPATH@/CMakeLists.txt",
            "cmake": {
                "vars": ['CMAKE_VERBOSE_MAKEFILE=ON']
            }
        }}
    ]
    for node in dict_of_tests:
        tedesc = tested.TEDescriptor("te_name",
            node,
            "label", 
            "subtree")
        
        assert(tedesc.name == "te_name")
        for i in tedesc.construct_tests():
            print(i.command)
