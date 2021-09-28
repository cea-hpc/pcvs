import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

import pcvs
from pcvs.backend import config as tested
from pcvs.backend.config import CONFIG_BLOCKS
from pcvs.helpers import utils
from pcvs.helpers.exceptions import ConfigException
from pcvs.helpers.system import MetaDict


@patch('glob.glob', return_value=[
            '/a/b/c/first.yml',
            '/a/b/c/second.yml'
        ])
def test_init(mock_glob):
    tested.init()
    assert(len(tested.CONFIG_BLOCKS) == 5)
    assert(len([elt for elt in ['compiler', 'runtime', 'group', 'criterion', 'machine'] if elt not in tested.CONFIG_BLOCKS]) == 0)

    for b in tested.CONFIG_BLOCKS:
        for s in utils.storage_order():
            node = tested.list_blocks(b, s)
            assert(len(node) == 2)
            assert(('first', '/a/b/c/first.yml') in node)
            assert(('second', '/a/b/c/second.yml') in node)
    
    tested.list_blocks('compiler')
            

    
@pytest.mark.parametrize("scope", [None, "local", "user", "global"])
@pytest.mark.parametrize("kind", ["compiler", "runtime", "machine", "criterion", "group"])
def test_config_init(kind, scope):
    obj = tested.ConfigurationBlock(kind, "test-name", scope)

    if scope is None:
        scope = 'local'
    assert(obj.scope == scope)
    assert(obj.full_name == "{}.{}.{}".format(scope, kind, "test-name"))
    assert(obj.short_name == "test-name")
    assert(not obj.is_found())
    obj.check()

def test_config_bad_kind():
    with pytest.raises(ConfigException.BadTokenError):
        tested.ConfigurationBlock("bad-kind", "test")

    with pytest.raises(ConfigException.BadTokenError):
        tested.ConfigurationBlock(None, "test")

@pytest.mark.parametrize("kind", ["compiler", "runtime", "machine", "criterion", "group"])
def test_config_load_template(kind, capsys):
    
    obj = tested.ConfigurationBlock(kind, "pcvs-pytest", 'local')
    assert(not obj.is_found())
    obj.load_template()
    obj.flush_to_disk()
    assert(obj.is_found())
    assert(obj.ref_file == os.path.join(utils.STORAGES['local'], kind, "pcvs-pytest.yml"))
    res = obj.dump()
    
    with open(os.path.join(
                    pcvs.PATH_INSTDIR,
                    "templates/config/{}.default.yml".format(kind)), 'r') as fh:
        ref = MetaDict(YAML(typ='safe').load(fh))
        assert(res == ref)
    
    obj.display()
    stream = capsys.readouterr().out
    assert("CONFIGURATION DISPLAY" in stream)
    assert("Scope: Local" in stream)
    assert("Path: {}".format(os.path.join(utils.STORAGES['local'], kind, "pcvs-pytest.yml")) in stream)
    obj.delete()

