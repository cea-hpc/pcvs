import pprint
import os
import glob
from addict import Dict
import shutil

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
        log.err("Failure while saving the banks.yml", '{}'.format(e))


class Bank:
    def __init__(self, name, bank_path=None):
        self._name = name
        self._data = Dict()
        self._datafile = None

        if bank_path is None and name in BANKS.keys():
            self._path = BANKS[self._name]
        else:
            self._path = str(bank_path)
        
        self._datafile = os.path.join(self._path, "data.yml")
        if os.path.isfile(self._datafile):
            #try:
            with open(self._datafile, 'r') as fh:
                self._data = Dict(yaml.load(fh, Loader=yaml.FullLoader))
            #except yaml.YAMLError:
            #    log.err("Error while loading bank data file")

    def flush(self):
        if os.path.isfile(self._datafile):
            try:
                with open(self._datafile, 'w') as fh:
                    yaml.dump(self._data.to_dict(), fh, default_flow_style=None)
            except yaml.YAMLError:
                log.err("Error while saving bank data file")

    def register(self):
        global BANKS
        BANKS[self._name] = self._path
        try:
            open(self._datafile, 'a').close()
        except FileExistsError as e:
            log.err('Registering a dir w/ existing data.yml ?')
    
    def unregister(self):
        global BANKS
        BANKS.pop(self._name, None)
        try:
            os.remove(self._datafile)
        except FileNotFoundError as e:
            pass

    def exists(self):
        global BANKS
        return len([i for i in BANKS.keys() if i == self._name]) == 1

    def save(self, k, v):
        # for now, only support archives
        if not os.path.isfile(v):
            log.err("Banks only support file submission (for now)")

        filename = os.path.basename(v)
        prefix = os.path.join(self._path, k)
        self._data[k] += [filename]
        if not os.path.exists(prefix):
            os.makedirs(prefix)
        shutil.copy(v, os.path.join(prefix, filename))
        self.flush()

    def load(self, k, dest=None):
        
        if dest is None:
            dest = os.getcwd()
        elif not os.path.exists(dest):
            os.makedirs(dest)

        if k not in self._data:
            log.err("No key named '{}'".format(k))
        
        for elt in self._data[k]:
            shutil.copy(os.path.join(self._path, k, elt),
                        os.path.join(dest, os.path.basename(elt)))

    def delete(self, k):
        if k not in self._data:
            log.err("No key named '{}'".format(k))
        
        shutil.rmtree(os.path.join(self._path, k))
        self._data.pop(k)
        self.flush()
    
    def show(self):
        log.print_section('Path: {}'.format(self._path))
        for k, v in self._data.items():
            log.print_section("{}:".format(k))
            for val in v:
                log.print_item('{}'.format(val))


