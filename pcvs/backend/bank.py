import os
import shutil
from pygit2.repository import Repository

import fcntl
import yaml
import time
from datetime import datetime, timezone
from addict import Dict
import pygit2

from pcvs.helpers import log, utils, criterion

BANKS = dict()
BANK_STORAGE = ""

class Bank2:
    def __init__(self, root_path, is_new=False):
        self._root = root_path
        self._repo = None
        self._new = is_new

    def __del__(self):
        self.disconnect_repository()
    
    def disconnect_repository(self):
        if self._locked:
            self._locked = False
            fcntl.flock(self._lockfile, fcntl.LOCK_UN)

    def connect_repository(self):
        if self._repo is None:
            if self._new:
                self._repo = pygit2.init_repository(
                    self._root,
                    flags=(pygit2.GIT_REPOSITORY_INIT_MKPATH |
                           pygit2.GIT_REPOSITORY_INIT_BARE |
                           pygit2.GIT_REPOSITORY_INIT_NO_REINIT),
                    mode=pygit2.GIT_REPOSITORY_INIT_SHARED_GROUP,
                    bare=True
                )
                #can't be moved before as self._root may not exist yet
                self._lockfile = open(os.path.join(self._root, ".pcvs.lock"), 'w+')
            else:
                rep = pygit2.discover_repository(self._root)
                if rep:
                    # need to lock, to ensure safety
                    self._root = rep
                    self._lockfile = open(os.path.join(self._root, ".pcvs.lock"), 'w+')            
                    locked = False
                    while not locked:
                        try:
                            fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            locked = True
                        except BlockingIOError:
                            time.sleep(1)

                    self._repo = pygit2.Repository(rep)
                else:
                    raise Exception
            self._locked = True

    def insert(self, treebuild, path, obj):
        repo = self._repo
        path_parts = path.split('/', 1)
        if len(path_parts) == 1:  # base case
            blob_obj = self.create_test_blob(obj)
            treebuild.insert(path, blob_obj, pygit2.GIT_FILEMODE_BLOB)
            return treebuild.write()

        subtree_name, sub_path = path_parts
        tree = repo.get(treebuild.write())
        
        try:
            entry = tree[subtree_name]
            assert(entry.filemode == pygit2.GIT_FILEMODE_TREE)
            subtree = repo.get(entry.hex)
            sub_treebuild = repo.TreeBuilder(subtree)
        except KeyError:
            sub_treebuild = repo.TreeBuilder()
        
        subtree_oid = self.insert(sub_treebuild, sub_path, obj)
        treebuild.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuild.write()


    def create_test_blob(self, data):
        assert(isinstance(self._repo, pygit2.Repository))
        assert(isinstance(data, str))

        data_hash = pygit2.hash(data)
        if data_hash in self._repo:
            return self._repo[data_hash].oid
        else:
            return self._repo.create_blob(data)

    def walkthrough_test_to_submit(self, config):
        """From the given archive, build the whole tree to store job results"""
        root_tree = self._repo.TreeBuilder()
        #TODO: need a test walkthrough (not dirs)
        for label, path in config.validation.dirs.items():
            for root, dirs, files in os.walk(path):
                for f in files:
                    if not (f.startswith('output-') and f.endswith('.json')):
                        continue

                    with open(os.path.join(root, f), 'r') as fh:
                        data = Dict(yaml.load(fh, Loader=yaml.FullLoader))
                    
                    for elt in data['tests']:
                        oid = self.insert(
                            root_tree, elt.full_name, elt.to_dict())
                        root_tree.insert(path, oid, pygit2.GIT_FILEMODE_TREE)
        return root_tree.write()
    
    def save_run_from_json(self, tag, data):
        log.warn("WIP")

    def save_run_from_buildir(self, tag, test_suite_path):
        """Process a test-suite build path to store it into the bank"""
        # first, load the conf.yml to retrieve useful informations
        conf_file = os.path.join(test_suite_path, "conf.yml")
        if not os.path.isfile(conf_file):
            log.err("{} is not a valid prefix".format(test_suite_path))
        
        with open(conf_file, 'r') as fh:
            config = Dict(yaml.load(fh, Loader=yaml.FullLoader))

        root_tree = self.walkthrough_test_to_submit(config)
        
        # Setup commit metadata:
        # 1. The author is the one who ran the test-suite
        # 2. The committer is submitting the archive to the bank
        # 3. the commit message is not relevant for now
        # 4. Timezone is not (yet) handled in author signature
        author = pygit2.Signature(
            name=config.validation.author.name,
            email=config.validation.author.email,
            time=int(config.validation.datetime.timestamp())
            )
        committer = pygit2.Signature(
            name=utils.get_current_username(),
            email=utils.get_current_usermail())
        commit_msg = "Commit message is not used (yet)"

        # a reference (lightweight branch) is tracking a whole test-suite
        # history, there are managed directly
        # TODO: compute the proper name for the current test-suite
        refname = "refs/heads/{}/{}".format(tag, config.validation.pf_hash)

        # check if the current reference already exit.
        # if so, retrieve the parent commit to be linked
        if refname in self._repo.references:
            parent_commit, ref = self._repo.resolve_refish(refname)
            parent_coid = [parent_commit.oid]
        else:
            # otherwise the commit to be created will be the first
            # and won't have any parent
            parent_coid = []
            ref = Dict({"name": None})

        # create the commit
        # ref.name may be None
        # parent_coid may be []
        coid = self._repo.create_commit(
            ref.name, author, committer, commit_msg, root_tree, parent_coid
        )

        # in case this is the first time the test-suite is added
        # --> create the reference to track history
        if ref.name is None:
            self._repo.references.create(refname, coid)

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
                    yaml.dump(self._data.to_dict(), fh,
                              default_flow_style=None)
            except yaml.YAMLError:
                log.err("Error while saving bank data file")

    def register(self):
        """create a new bank and save it on disk"""
        global BANKS
        BANKS[self._name] = self._path
        try:
            open(self._datafile, 'a').close()
        except FileExistsError:
            log.err('Registering a dir w/ existing data.yml ?')

    def unregister(self):
        """delete a previously registered bank.
        Note this won't delete the directory itself but any PCVS relatives
        """
        global BANKS
        BANKS.pop(self._name, None)
        try:
            os.remove(self._datafile)
        except FileNotFoundError:
            pass

    def exists(self):
        """
            check if current bank is actually registered
            into global management
        """
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
