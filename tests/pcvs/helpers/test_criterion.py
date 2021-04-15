from unittest.mock import patch

import pytest
from addict import Dict

from pcvs.helpers import criterion as tested


@pytest.fixture()
def crit_desc():
    return {
        "arg": tested.Criterion(name="arg", numeric=True, description={
            "option": "-a ",
            "type": "argument",
            "subtitle": "A=",
            "values": [2, 4]
        }),
        "env": tested.Criterion(name="env", description={
            "option": "ENV=",
            "type": "environment",
            "subtitle": "E=",
            "values": ["a"]
        }),
        "prog-env": tested.Criterion(name="prog-env", local=True, description={
            "option": "PROG_ENV=",
            "type": "environment",
            "subtitle": "pe=",
            "values": ["f"]
        }),
        "prog-arg": tested.Criterion(name="prog-arg", local=True, description={
            "option": "-pa ",
            "type": "argument",
            "subtitle": "pa=",
            "values": ["arg1", "arg2"]
        })
    }

@pytest.fixture()
def crit_comb():
    return {
        "arg": 10,
        "env": "message",
        "prog-env": "user_message",
        "prog-arg": "parameter"
    }

def test_combination_init(crit_desc, crit_comb):
    obj = tested.Combination(crit_desc, crit_comb)
    assert(obj.get('arg') == 10)
    assert(obj.get('env') == "message")
    assert(obj.get('prog-env') == "user_message")
    assert(obj.get('prog-arg') == "parameter")

def test_combination_str(crit_desc, crit_comb):
    obj = tested.Combination(crit_desc, crit_comb)
    assert(obj.translate_to_str() == "A=10_E=message_pa=parameter_pe=user_message")

    crit_desc['arg'] = tested.Criterion(name="arg", numeric=True, description={
            "option": "-a ",
            "type": "argument",
            "subtitle": ""
        })
    obj = tested.Combination(crit_desc, crit_comb)
    assert(obj.translate_to_str() == "10_E=message_pa=parameter_pe=user_message")

    crit_desc['arg'] = tested.Criterion(name="arg", numeric=True, description={
            "option": "-a ",
            "type": "argument"
        })
    obj = tested.Combination(crit_desc, crit_comb)
    assert(obj.translate_to_str() == "E=message_pa=parameter_pe=user_message")

def test_combination_command(crit_desc, crit_comb):
    obj = tested.Combination(crit_desc, crit_comb)
    env, args, params = obj.translate_to_command()
    assert(['ENV=message', 'PROG_ENV=user_message'] == env)
    assert(['-a 10'] == args)
    assert(['-pa parameter'] == params)


def test_serie_init(crit_desc):
    obj = tested.Serie(crit_desc)
