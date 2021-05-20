import os
from unittest.mock import patch

import pytest
from addict import Dict

import pcvs
from pcvs.helpers import exceptions, pm, system
from pcvs.testing import tedesc as tested


@patch('pcvs.helpers.system.MetaConfig.root', Dict({
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
    

@patch('pcvs.helpers.system.MetaConfig.root', Dict({
            'compiler': {
                'variants': {
                    'openmp': {'args': '-fopenmp'},
                    'other_variant': {'args': '-fvariant'},
                    'all_errors': {'args': '-Werror'}
                }
            }}))
def test_build_variants():
    print(system.MetaConfig.root.compiler.variants)
    assert("-fopenmp" in tested.prepare_cmd_build_variants(['openmp']))

    s = tested.prepare_cmd_build_variants(['openmp', 'all_errors'])
    assert(all(x in s for x in ['-fopenmp', '-Werror']))
    assert('-fvariant' not in s)


@patch('pcvs.helpers.pm.identify')
def test_handle_job_deps(mock_id):
    #mock_pmlister.return_value = 
    assert(tested.handle_job_deps({'depends_on': {
        'test': ['a', 'b', 'c']
    }}, "label", "prefix") == ["label/prefix/a", "label/prefix/b", "label/prefix/c"])

    assert(tested.handle_job_deps({'depends_on': {
        'test': ['/a', '/b', '/c']
    }}, "label", "prefix") == ["/a", "/b", "/c"])

    mock_id.return_value = ["spack..p1", "spack..p1c2", "spack..p1p3%c4"]
    assert(len(tested.handle_job_deps({'depends_on': {
        'pm': ['p1', 'p1@c2', 'p1 p3 %c4']
    }}, "label", "prefix")) == 3)

    assert(len(tested.handle_job_deps({}, "", "")) == 0)


@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
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
def test_TEDescriptor():
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
