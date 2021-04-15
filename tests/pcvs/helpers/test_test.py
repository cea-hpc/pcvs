import os
from unittest.mock import patch

import pytest
from unittest.mock import patch
from pcvs.helpers import test as tested


def legacy_yaml_file():
    assert(False)


def load_yaml_file():
    assert(False)

@patch.dict(os.environ, {'HOME': '/home/user', 'USER': 'superuser'})
def test_replace_tokens():
    build = "/path/to/build"
    prefix = "dir1/dir2"
    src = "/path/to/src"

    assert(tested.replace_special_token(
                'build curdir is @BUILDPATH@',
                src, build, prefix
    ) == 'build curdir is /path/to/build/dir1/dir2')

    assert(tested.replace_special_token(
                'src curdir is @SRCPATH@',
                src, build, prefix
    ) == 'src curdir is /path/to/src/dir1/dir2')

    assert(tested.replace_special_token(
                'src rootdir is @ROOTPATH@',
                src, build, prefix
    ) == 'src rootdir is /path/to/src')

    assert(tested.replace_special_token(
                'build rootdir is @BROOTPATH@',
                src, build, prefix
    ) == 'build rootdir is /path/to/build')

    assert(tested.replace_special_token(
                'HOME is @HOME@',
                src, build, prefix
    ) == 'HOME is {}'.format("/home/user"))

    assert(tested.replace_special_token(
                'USER is @USER@',
                src, build, prefix
    ) == 'USER is {}'.format("superuser"))
