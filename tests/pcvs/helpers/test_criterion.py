from unittest.mock import patch

import pytest

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


matrix = {
    "arithmetic": [
        ({"from": 0, "to": 10}, {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
        ({"from": 1, "to": 10, "of": 3}, {1, 4, 7, 10}),
        ({"from": 0, "to": 100, "of": 10}, {0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100}),
        ({"from": 100, "to": 20, "of": -11}, {100, 89, 78, 67, 56, 45, 34, 23})
    ],
    "geometric": [
        ({"from": 0, "to": 10}, {0}),
        ({"from": 10, "to": 100, "of": 0}, {1}),
        ({"from": 10, "to": 100, "of": -1}, {0.1}),
        ({"from": 1, "to": 100, "of": 2}, {1, 2, 4, 8, 16, 32, 64}),
        ({"from": 1, "to": 100, "of": 3}, {1, 3, 9, 27, 81}),
    ],
    "powerof": [
        ({"from": 0, "to": 10}, {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
        ({"from": 2, "to": 4, "of": 0.5}, {
            2.0, 2.23606797749979, 2.449489742783178, 2.6457513110645907,
            2.8284271247461903, 3.0, 3.1622776601683795, 3.3166247903554,
            3.4641016151377544, 3.605551275463989, 3.7416573867739413,
            3.872983346207417, 4.0}),
        ({"from": 0, "to": 10, "of": 3}, {0, 1, 8}),
        ({"from": 0, "to": 1000000, "of": 10}, {0, 1, 1024, 59049})
    ]
}

@pytest.mark.parametrize("op", ["arithmetic", "geometric", "powerof"])
def test_value_expansion(op):
    d = {
        "numeric": True,
        "option": "-np ",
        "position": "after",
        "subtitle": "n"
    }
    for elt in matrix[op]:
        c = tested.Criterion("n_mpi", {**d, "values": [{**elt[0], "op": op}]})
        c.expand_values()
        assert(c.values == elt[1])

def test_serie_init(crit_desc):
    obj = tested.Serie(crit_desc)

