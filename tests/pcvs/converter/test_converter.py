import os

import pytest
from ruamel.yaml import YAML

from .conftest import click_call, isolated_fs


def test_exec():
    ret = click_call("--help")
    assert(ret.exit_code == 0)
    ret = click_call("--version")
    assert(ret.exit_code == 0)


def test_simple_run():
    with isolated_fs():
        f = os.path.join(os.getcwd(), "test.yml")
        with open(f, "w") as fh:
            YAML().dump({
                "simple_counter_std_thread": {
                "type": "complete",
                "cargs": "-lpthread",
                "files": "@SRCPATH@/simple_counter.cpp",
                "bin": "simple_counter_std_thread",
                "n_proc": None,
                "n_mpi": None,
                "n_omp": None,
                "net": None
            }}, fh)

        ret = click_call('-k', 'te', '--stdout', f)
        assert(ret.exit_code == 0)
        assert("Converted data written into <stdout>" in ret.stdout)
        assert("simple_counter_std_thread:" in ret.stdout)

        ret = click_call('-k', 'te', f)
        assert(ret.exit_code == 0)
        assert(os.path.exists(os.path.join(os.getcwd(), "convert-test.yml")))
        