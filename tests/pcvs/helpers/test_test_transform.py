from pcvs.helpers import test_transform as tested
import pcvs
import pytest
from addict import Dict
from unittest.mock import patch

@patch('pcvs.helpers.system.get', return_value=Dict({
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
        }))
def test_lang_detection(mock_sys):
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
    

@patch('pcvs.helpers.system.get', return_value=Dict({
            'variants': {
                'openmp': {'args': '-fopenmp'},
                'other_variant': {'args': '-fvariant'},
                'all_errors': {'args': '-Werror'}
            }
        }))
def test_build_variants(mock_sys):
    assert("-fopenmp" in tested.prepare_cmd_build_variants(['openmp']))

    s = tested.prepare_cmd_build_variants(['openmp', 'all_errors'])
    assert(all(x in s for x in ['-fopenmp', '-Werror']))
    assert('-fvariant' not in s)


@patch('pcvs.helpers.package_manager.identify')
def handle_job_deps(mock_pmlister):
    #mock_pmlister.return_value = 
    assert(tested.handle_job_deps({'depends_on': {
        'test': ['a', 'b', 'c']
    }}, "prefix") == ["prefix/a", "prefix/b", "prefix/c"])

    assert(tested.handle_job_deps({'depends_on': {
        'test': ['/a', '/b', '/c']
    }}, "prefix") == ["/a", "/b", "/c"])

    assert(len(tested.handle_job_deps({'depends_on': {
        'pm': ['p1', 'p1@c2', 'p1 p3 %c4']
    }}, "prefix")) == 3)
