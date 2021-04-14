from unittest.mock import patch

import pytest

from pcvs.backend import config as tested
from pcvs.backend.config import CONFIG_BLOCKS
from pcvs.helpers import utils


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
            assert(len(tested.CONFIG_EXISTING[b][s]) == 2)
            assert(('first', '/a/b/c/first.yml') in tested.CONFIG_EXISTING[b][s])
            assert(('second', '/a/b/c/second.yml') in tested.CONFIG_EXISTING[b][s])
    