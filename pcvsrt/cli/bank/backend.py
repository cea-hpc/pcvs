import os
import glob

import yaml

from pcvsrt.helpers import io, log

BANKS = dict()
BANK_STORAGE=""

def init():
    global BANKS, BANK_STORAGE
    BANK_STORAGE = os.path.join(io.STORAGES['user'], "saves/banks.yml")
    try:
        with open(BANK_STORAGE, 'r') as f:
            BANKS = yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError:
        pass


def list_banks():
    return BANKS


def flush_to_disk():
    global BANKS, BANK_STORAGE
    try:
        with open(BANK_STORAGE, 'w') as f:
            yaml.dump(BANKS, f)
    except IOError as e:
        log.err("Failure while saving the banks.yml", '{}'.format(e), abort=1)


class Bank:
    def __init__(self, name, bank_path=None):
        self._name = name

        if bank_path is None and name in BANKS.keys():
            self._path = BANKS[self._name]

    def register(self):
        BANKS[self._name] = self._path
    
    def exists(self):
        global BANKS
        return len([i for i in BANKS.keys() if i == self._name]) == 1

    def save(self, k, v):
        pass

    def load(self, k):
        pass

