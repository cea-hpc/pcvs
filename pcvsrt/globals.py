import os
from os import path


def __determine_local_prefix():
    return os.path.join(os.getcwd(), ".pcvsrt")


ROOTPATH = path.abspath(path.join(path.dirname(__file__)))
STORAGES = {
    'global': ROOTPATH,
    'user': os.environ['HOME'],
    'local': __determine_local_prefix()
}
