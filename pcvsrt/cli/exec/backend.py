import os
import yaml

from pcvsrt.helpers import io, log

def retrieve_all_test_scripts(output=None):
    if output is None:
        output = "./.pcvs/test_suite"
    l = list()
    for root, _, files in os.walk(output):
        for f in files:
            if f == 'list_of_tests.sh':
                l.append(os.path.join(root, f))
    return l
    
def retrieve_test_script(testname, output=None):
    if output is None:
        output = "./.pcvs/test_suite"
    # first one is directory name
    # last one is test name
    prefix = testname.split('.')[:-1]
    return os.path.join(
        output,
        "/".join(prefix),
        "list_of_tests.sh"
    )
