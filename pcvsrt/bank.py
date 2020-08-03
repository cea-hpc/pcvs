import os
import glob

from pcvsrt import globals as pvGlobals


BANKS = dict()
BANKS_STORAGE = ""


def init():
    global BANKS, BANKS_STORAGE
    BANKS_STORAGE = os.path.join(pvGlobals.STORAGES['user'], 'saves/banks')
    for f in glob.glob(os.path.join(BANKS_STORAGE, '*')):
        BANKS[os.path.basename(f)] = open(f, 'r').read()


def list_banks():
    return BANKS

def compute_path(name):
    return os.path.join(BANKS_STORAGE, name)



class Bank:
    def __init__(self, name, bank_path):
        self._bank_path = bank_path
        self._file = compute_path(name)
    
    def exists(self):
        return os.path.isfile(self._file)
    
    def flush_to_disk(self):

        if not os.path.isdir(BANKS_STORAGE):
            os.makedirs(BANKS_STORAGE)
        
        with open(self._file, 'w') as f:
            f.write(self._bank_path)
