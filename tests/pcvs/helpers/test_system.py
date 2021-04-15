import os
from logging import error
from unittest.mock import patch

import jsonschema
import pytest
import yaml
from addict import Dict

import pcvs
from pcvs import PATH_INSTDIR
from pcvs.helpers import package_manager
from pcvs.helpers import system
from pcvs.helpers import system as s
from pcvs.helpers import utils


def test_bootstrap_compiler():
    obj = s.MetaConfig()
    obj.bootstrap_compiler({
        "commands": {
            "cc": "/path/to/cc"
        },
        "variants": {
            "openmp": {
                "args": "-fopenmp"
            }
        },
        "package_manager": {
            "spack" : ["mypackage@myversion"],
            "module": ["mod1", "mod2"]
        }}
    )
    assert(isinstance(obj.compiler, s.Config))
    assert(obj.compiler.commands.cc == "/path/to/cc")
    assert(obj.compiler.variants.openmp.args == "-fopenmp")
    
    assert(isinstance(obj.compiler.package_manager.spack, list))
    assert(len(obj.compiler.package_manager.spack) == 1)
    assert(isinstance(obj.compiler.package_manager.module, list))
    assert(len(obj.compiler.package_manager.module) == 2)

    package_array = obj.get_internal('cc_pm')
    res = dict()
    assert(isinstance(package_array, list))
    assert(len(package_array) == 3)
    for p in package_array:
        assert(isinstance(p, package_manager.PManager))
        if type(p) in res:
            res[type(p)] += 1
        else:
            res[type(p)] = 1
    assert(res[package_manager.SpackManager] == 1)
    assert(res[package_manager.ModuleManager] == 2)

def test_bootstrap_runtime():
    obj = s.MetaConfig()
    obj.bootstrap_runtime({
        "program": "/path/to/rt",
        "iterators": {
            "n_mpi": {
                "numeric": True
            }
        },
        "package_manager": {
            "spack" : ["mypackage@myversion"],
            "module": ["mod1", "mod2"]
        }}
    )
    assert(isinstance(obj.runtime, s.Config))
    assert(obj.runtime.program == "/path/to/rt")
    assert(obj.runtime.iterators.n_mpi.numeric)
    
    assert(isinstance(obj.runtime.package_manager.spack, list))
    assert(len(obj.runtime.package_manager.spack) == 1)
    assert(isinstance(obj.runtime.package_manager.module, list))
    assert(len(obj.runtime.package_manager.module) == 2)

    package_array = obj.get_internal('rt_pm')
    res = dict()
    assert(isinstance(package_array, list))
    assert(len(package_array) == 3)
    for p in package_array:
        assert(isinstance(p, package_manager.PManager))
        if type(p) in res:
            res[type(p)] += 1
        else:
            res[type(p)] = 1
    assert(res[package_manager.SpackManager] == 1)
    assert(res[package_manager.ModuleManager] == 2)

@pytest.fixture
def kw_keys():
    return [f.replace('-scheme.yml', '') for f in os.listdir(os.path.join(PATH_INSTDIR, 'schemes/'))]

@pytest.fixture
def init_config():
    d = Dict({"": "value1", "key2": "value2"})
    conf = system.Config(d)

def test_validate(kw_keys):
    vs = system.Config()
    compiler = {
        "commands": {
            "cc": "example",
            "cxx": "example",
            "fc": "example",
            "f77": "example",
            "f90" : "example",
        },
        "variants": {
            "openmp": {"args": "example"},
            "tbb": {"args": "example"},
            "cuda": {"args" : "example"},
            "strict": {"args" : "example"}
        },
        "package_manager": {
            "spack": ["example"],
            "module": ["example"]
        }
    }    
    runtime = {
        "program": "example",
        "args": "example",
        "iterators": {
            "iterator_name": {
                "option": "example",
                "numeric": True,
                "type": "argument",
                "position": "before",
                "aliases": {
                    "ib": "example",
                    "tcp": "example",
                    "shmem": "example",
                    "ptl": "example"
                }
            }
        },
        "package_manager": {
            "spack": ["example"],
            "module": ["example"]
        }
    }
    criterion = {
        "iterators":{
            "example":{
                "values": [1,2],
                "subtitle": "example"
            }
        }
    }
    criterion_wrong = {
        "wrong-key":{
            "example":{
                "values": [1,2],
                "subtitle": "example"
            }
        }
    }
    keywords = [
        (compiler, "compiler"), 
        (runtime, "runtime"), 
        (criterion, "criterion")
    ]
    # for kw in ["compiler", "criterion", "group"]:
    #     with open(os.path.join(PATH_INSTDIR, "templates/{}-format.yml".format(kw))) as blk:
    #         to_validate = Dict(yaml.load(blk))
    #         conf = system.Config(to_validate)
    #         conf.validate(kw)
    for kw in keywords:
        to_validate = Dict(kw[0])
        conf = system.Config(to_validate)
        conf.validate(kw[1])
    with pytest.raises(pcvs.helpers.exceptions.ValidationException.FormatError):
        to_validate = Dict(criterion_wrong)
        conf = system.Config(to_validate)
        conf.validate(kw[1])
    with pytest.raises(AssertionError):
        vs.validate("wrong_value")


def test_config(init_config):
    pass
