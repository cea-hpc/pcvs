import os
from unittest.mock import patch

import pytest

import pcvs
from pcvs import PATH_INSTDIR
from pcvs.helpers import pm
from pcvs.helpers import system
from pcvs.helpers import system as s
from pcvs.helpers.system import MetaDict


def test_bootstrap_compiler():
    obj = s.MetaConfig()
    obj.bootstrap_compiler({
        "cc": {
            "program": "/path/to/cc",
            "variants": {
                "openmp": {
                    "args": "-fopenmp"
                }
            }
        },
        "package_manager": {
            "spack" : ["mypackage@myversion"],
            "module": ["mod1", "mod2"]
        }}
    )
    assert(isinstance(obj.compiler, s.Config))
    assert(obj.compiler.cc.program == "/path/to/cc")
    assert(obj.compiler.cc.variants.openmp.args == "-fopenmp")
    
    assert(isinstance(obj.compiler.package_manager.spack, list))
    assert(len(obj.compiler.package_manager.spack) == 1)
    assert(isinstance(obj.compiler.package_manager.module, list))
    assert(len(obj.compiler.package_manager.module) == 2)

    package_array = obj.get_internal('cc_pm')
    res = dict()
    assert(isinstance(package_array, list))
    assert(len(package_array) == 3)
    for p in package_array:
        assert(isinstance(p, pm.PManager))
        if type(p) in res:
            res[type(p)] += 1
        else:
            res[type(p)] = 1
    assert(res[pm.SpackManager] == 1)
    assert(res[pm.ModuleManager] == 2)

def test_bootstrap_runtime():
    obj = s.MetaConfig()
    obj.bootstrap_runtime({
        "program": "/path/to/rt",
        "criterions": {
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
    assert(obj.runtime.criterions.n_mpi.numeric)
    
    assert(isinstance(obj.runtime.package_manager.spack, list))
    assert(len(obj.runtime.package_manager.spack) == 1)
    assert(isinstance(obj.runtime.package_manager.module, list))
    assert(len(obj.runtime.package_manager.module) == 2)

    package_array = obj.get_internal('rt_pm')
    res = dict()
    assert(isinstance(package_array, list))
    assert(len(package_array) == 3)
    for p in package_array:
        assert(isinstance(p, pm.PManager))
        if type(p) in res:
            res[type(p)] += 1
        else:
            res[type(p)] = 1
    assert(res[pm.SpackManager] == 1)
    assert(res[pm.ModuleManager] == 2)

@pytest.fixture
def kw_keys():
    return [f.replace('-scheme.yml', '') for f in os.listdir(os.path.join(PATH_INSTDIR, 'schemes/'))]

@pytest.fixture
def init_config():
    d = MetaDict({"": "value1", "key2": "value2"})
    conf = system.Config(d)

def test_validate(kw_keys):
    vs = system.Config()
    compiler = {
        "cc": {
            "program": "example",
            "variants": {
                "openmp": {"args": "example"},
                "tbb": {"args": "example"},
                "cuda": {"args" : "example"},
                "strict": {"args" : "example"},
            },
        },
        "cxx": {"program": "example"},
        "fc": {"program": "example"},
        "f77": {"program": "example"},
        "f90" : {"program": "example"},
        "package_manager": {
            "spack": ["example"],
            "module": ["example"]
        }
    }
    runtime = {
        "program": "example",
        "args": "example",
        "criterions": {
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
        "example":{
            "values": [1,2],
            "subtitle": "example"
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
    #         to_validate = MetaDict(yaml.load(blk))
    #         conf = system.Config(to_validate)
    #         conf.validate(kw)
    for kw in keywords:
        to_validate = MetaDict(kw[0])
        conf = system.Config(to_validate)
        conf.validate(kw[1])
    with pytest.raises(pcvs.helpers.exceptions.ValidationException.FormatError):
        to_validate = MetaDict(criterion_wrong)
        conf = system.Config(to_validate)
        conf.validate(kw[1])
    with pytest.raises(AssertionError):
        vs.validate("wrong_value")


def test_config(init_config):
    pass
