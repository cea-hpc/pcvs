import os
import yaml

from pcvsrt.helpers import io, log


def retrieve_test_script(testname):
    # first one is directory name
    # last one is test name
    prefix = testname.split('.')[:-1]
    return os.path.join(
        "./.pcvs/test_suite/",
        "/".join(prefix),
        "list_of_tests.sh"
    )
