import pytest
from pcvs.helpers import utils as tested

@pytest.mark.parametrize("token", ["test1", "test/test1"])
def test_token_extraction_1(token):
    assert(tested.extract_infos_from_token(token) == (None, None, token))
    assert(tested.extract_infos_from_token(token, single="right") == (None, None, token))
    assert(tested.extract_infos_from_token(token, single="center") == (None, token, None))
    assert(tested.extract_infos_from_token(token, single="left") == (token, None, None))

@pytest.mark.parametrize("token", ["runtime.test1", "compiler.test/test1"])
def test_token_extraction_2(token):
    split = token.split(".")
    assert(tested.extract_infos_from_token(token) == (None, split[0], split[1]))
    assert(tested.extract_infos_from_token(token, pair="right") == (None, split[0], split[1]))
    assert(tested.extract_infos_from_token(token, pair="span") == (split[0], None, split[1]))
    assert(tested.extract_infos_from_token(token, pair="left") == (split[0], split[1], None))

@pytest.mark.parametrize("token", ["local.runtime.test1",
                                   "global.compiler.test/test1"
                                   "global.comppiler.this.is.a.test"])
def test_token_extraction_3(token):
    split = token.split(".")
    assert(tested.extract_infos_from_token(token) == (split[0], split[1], ".".join(split[2:])))
