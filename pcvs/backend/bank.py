import glob
import os
import pprint
import shutil

import yaml
from addict import Dict

from pcvs.helpers import log, utils

BANKS = dict()
BANK_STORAGE=""


def init():
    """Called when program initializes. Detects defined banks in
    $USER_STORAGE/banks.yml
    """
    global BANKS, BANK_STORAGE
    BANK_STORAGE = os.path.join(utils.STORAGES['user'], "saves/banks.yml")
    try:
        with open(BANK_STORAGE, 'r') as f:
            BANKS = yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError:
        # nothing to do, file may not exist
        pass


def list_banks():
    """Accessor to bank dict (outside of this module)"""
    return BANKS


def flush_to_disk():
    """Save in-memory bank management to disk. This only implies 'banks.yml'"""
    global BANKS, BANK_STORAGE
    try:
        prefix_file = os.path.dirname(BANK_STORAGE)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)
        with open(BANK_STORAGE, 'w+') as f:
            yaml.dump(BANKS, f)
    except IOError as e:
        log.err("Failure while saving the banks.yml", '{}'.format(e))


class Bank:
    """A 'Bank' object manages persistent data between run(s) and test reports.
    A bank is initialized at a given mount point on the filesystem and stores
    data in it, following a label-based tree.
    """
    def __init__(self, name, bank_path=None):
        self._name = name
        self._data = Dict()
        self._datafile = None
        
        # If the bank 'path' is not defined but known from global config:
        if bank_path is None and name in BANKS.keys():
            self._path = BANKS[self._name]
        else:
            self._path = str(bank_path)
        
        # attempt to load file management configuration stored into the bank
        self._datafile = os.path.join(self._path, "data.yml")
        if os.path.isfile(self._datafile):
            try:
                with open(self._datafile, 'r') as fh:
                    self._data = Dict(yaml.load(fh, Loader=yaml.FullLoader))
            except yaml.YAMLError:
                log.err("Error while loading bank data file")

    def flush(self):
        """save the current bank into its own 'data.yml' file"""
        if os.path.isfile(self._datafile):
            try:
                with open(self._datafile, 'w') as fh:
                    yaml.dump(self._data.to_dict(), fh, default_flow_style=None)
            except yaml.YAMLError:
                log.err("Error while saving bank data file")

    def register(self):
        """create a new bank and save it on disk"""
        global BANKS
        BANKS[self._name] = self._path
        try:
            open(self._datafile, 'a').close()
        except FileExistsError as e:
            log.err('Registering a dir w/ existing data.yml ?')
    
    def unregister(self):
        """delete a previously registered bank.
        Note this won't delete the directory itself but any PCVS relatives
        """
        global BANKS
        BANKS.pop(self._name, None)
        try:
            os.remove(self._datafile)
        except FileNotFoundError as e:
            pass

    def exists(self):
        """check if current bank is actually registered into global management"""
        global BANKS
        return len([i for i in BANKS.keys() if i == self._name]) == 1

    def save(self, k, v):
        """store a new data (v) into the current bank, labeled 'k' """
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
        """load something (v) from the current bank, under label 'k' """
        if dest is None:
            dest = os.getcwd()
        elif not os.path.exists(dest):
            os.makedirs(dest)

        if k not in self._data:
            log.err("No key named '{}'".format(k))
        
        # copy full content
        for elt in self._data[k]:
            shutil.copy(os.path.join(self._path, k, elt),
                        os.path.join(dest, os.path.basename(elt)))

    def delete(self, k):
        """Delete data from a the current bank"""
        if k not in self._data:
            log.err("No key named '{}'".format(k))
        
        shutil.rmtree(os.path.join(self._path, k))
        self._data.pop(k)
        self.flush()
    
    def show(self):
        """List bank's content"""
        log.print_section('Path: {}'.format(self._path))
        for k, v in self._data.items():
            log.print_section("{}:".format(k))
            for val in v:
                log.print_item('{}'.format(val))
