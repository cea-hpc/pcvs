from pcvs.backend.config import CONFIG_BLOCKS
from pcvs.backend import config as tested
from pcvs.helpers import utils
import pytest
import glob




def test_init(monkeypatch):
    def mockglob(path):
        return [
            '/a/b/c/first.yml',
            '/a/b/c/second.yml'
        ]
    monkeypatch.setattr(glob, 'glob', mockglob)
    
    tested.init()
    assert(len(tested.CONFIG_BLOCKS) == 5)
    assert(len([elt for elt in ['compiler', 'runtime', 'group', 'criterion', 'machine'] if elt not in tested.CONFIG_BLOCKS]) == 0)

    for b in tested.CONFIG_BLOCKS:
        for s in utils.storage_order():
            assert(len(tested.CONFIG_EXISTING[b][s]) == 2)
            assert(('first', '/a/b/c/first.yml') in tested.CONFIG_EXISTING[b][s])
            assert(('second', '/a/b/c/second.yml') in tested.CONFIG_EXISTING[b][s])
    