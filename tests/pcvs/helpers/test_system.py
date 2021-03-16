from addict import Dict
import pytest
import os
import yaml
from pcvs.helpers import package_manager, utils
from pcvs.helpers import system as s
from unittest.mock import patch


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
