from addict import Dict
import pytest
import os
import yaml
from pcvs.helpers import package_manager
from pcvs.helpers import system as s
from unittest.mock import patch


def test_save_global_object():
    obj = s.Settings()
    s.save_as_global(obj)
    assert(obj is s.sysTable)


def test_global_getter():
    obj = s.Settings()
    obj.item_a = 'value_a'
    obj.item_b.subitem_c = 'value_b'

    s.save_as_global(obj)
    
    assert(s.get() is obj)
    assert(s.get('item_a') is obj.item_a)
    assert(s.get('item_b').subitem_c is obj.item_b.subitem_c)


def test_serialize():
    obj = s.Settings()
    obj.a.b = 2
    obj.c.d.e = 10
    assert(obj.serialize() == {
        'a': {
            'b': 2
        },
        'c': {
            'd': {
                'e': 10
            }
        }
    })


@patch('yaml.load', return_value={})
def test_cfg_validation(mock_load):
    obj = s.CfgValidation()
    assert(obj.color is True)
    assert(obj.simulated is False)
    assert(obj.dirs == ".")
    assert(obj.pf_name == "default")
    assert(obj.result.format == ['json'])

def test_cfg_machine():
    obj = s.CfgMachine({})
    for k in [
        'nodes', 'cores_per_node', 'concurrent_run'
    ]:
        assert(k in obj)

def test_cfg_compiler():
    obj = s.CfgCompiler({
        'package_manager': {'spack': ['jchronoss%gcc']}
    })
    assert(obj is not None)
    for i in obj.obj:
        assert(isinstance(i, package_manager.PManager))

