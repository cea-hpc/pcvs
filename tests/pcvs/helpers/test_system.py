from addict import Dict
import pytest

from pcvsrt.helpers import system as s


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

def test_cfg_validation():
    obj = s.CfgValidation({})
    for k in [
        'verbose', 'color', 'pf_name', 'output', 'background',
        'override', 'dirs', 'xmls', 'simulated', 'anonymize', 'exported_to'
    ]:
        assert(k in obj)

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
    assert(self.obj is not None)
    for i in self.obj:
        assert(isinstance(self.obj, PManager))

