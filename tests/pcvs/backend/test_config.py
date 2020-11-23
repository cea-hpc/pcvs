from pcvs.backend.config import CONFIG_BLOCKS
from pcvs.backend import config as tested
from pcvs.helpers import utils
import pytest
import glob


@pytest.mark.parametrize("token", ["test1", "test/test1"])
def test_token_extraction_1(token):
    assert(tested.extract_config_from_token(token) == (None, None, token))
    assert(tested.extract_config_from_token(token, single="right") == (None, None, token))
    assert(tested.extract_config_from_token(token, single="center") == (None, token, None))
    assert(tested.extract_config_from_token(token, single="left") == (token, None, None))

@pytest.mark.parametrize("token", ["runtime.test1", "compiler.test/test1"])
def test_token_extraction_2(token):
    split = token.split(".")
    assert(tested.extract_config_from_token(token) == (None, split[0], split[1]))
    assert(tested.extract_config_from_token(token, pair="right") == (None, split[0], split[1]))
    assert(tested.extract_config_from_token(token, pair="span") == (split[0], None, split[1]))
    assert(tested.extract_config_from_token(token, pair="left") == (split[0], split[1], None))

@pytest.mark.parametrize("token", ["local.runtime.test1", "global.compiler.test/test1"])
def test_token_extraction_3(token):
    split = token.split(".")
    assert(tested.extract_config_from_token(token) == (split[0], split[1], split[2]))


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
    