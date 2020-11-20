from pcvs.helpers import test_transform as tested
import pytest
from addict import Dict
from pcvs.helpers import system, package_manager


def test_lang_detection(monkeypatch):
    def compiler_get(token):
        return Dict({
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
        })
    
    monkeypatch.setattr(system, 'get', compiler_get)

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
    

def test_build_variants(monkeypatch):
    def mock_compiler_variants(token):
        return Dict({
            'variants': {
                'openmp': {'args': '-fopenmp'},
                'other_variant': {'args': '-fvariant'},
                'all_errors': {'args': '-Werror'}
            }
        })
    monkeypatch.setattr(system, "get", mock_compiler_variants)
    assert("-fopenmp" in tested.prepare_cmd_build_variants(['openmp']))

    s = tested.prepare_cmd_build_variants(['openmp', 'all_errors'])
    assert(all(x in s for x in ['-fopenmp', '-Werror']))
    assert('-fvariant' not in s)


def test_handle_job_deps(monkeypatch):
    def mock_pm(keyval):
        s = list()
        for k, v in keyval.items():
            for vv in v:
                s.append(package_manager.PManager())
        return s

    monkeypatch.setattr(package_manager, 'identify', mock_pm)
    assert(tested.handle_job_deps({'depends_on': {
        'test': ['a', 'b', 'c']
    }}, "prefix") == ["prefix/a", "prefix/b", "prefix/c"])

    assert(tested.handle_job_deps({'depends_on': {
        'test': ['/a', '/b', '/c']
    }}, "prefix") == ["/a", "/b", "/c"])

    assert(len(tested.handle_job_deps({'depends_on': {
        'pm': ['p1', 'p1@c2', 'p1 p3 %c4']
    }}, "prefix")) == 3)
