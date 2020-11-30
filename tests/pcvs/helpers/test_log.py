from pcvs.helpers import log as tested
import pytest
import logging

@pytest.mark.parametrize("level", [(0, "normal", logging.WARNING), 
                                   (1, "info", logging.INFO),
                                   (2, "debug", logging.DEBUG)])
def test_logger(level):
    tested.__set_logger(level[0])
    assert(tested.get_verbosity(level[1]) == True)
    assert(tested.get_verbosity_str() == level[1])
    assert(logging.getLogger().getEffectiveLevel() == level[2])
