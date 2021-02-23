import os
import tarfile
import tempfile
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

class Bank:
    def __init__(self, root_path=None, name="default", is_new=False):
        self._root = root_path
        self._repo = None
        self._new = is_new
        self._config = None
        self._rootree = None
        self._name = name
        self._locked = False

        global BANKS
        if name.lower() in BANKS.keys():
            self._root = BANKS[name.lower()]
        
        assert(self._root is not None)

    @property
    def prefix(self):
        return self._root
    
    @property
    def name(self):
        return self._name

    def exists(self):
        return self._root is not None and os.path.isdir(self._root)

    def list_projects(self):
        INVALID_REFS = ["refs/heads/master"]
        # a ref is under the form: 'refs/<bla>/NAME/<hash>
        return [elt.split('/')[2] for elt in self._repo.references if elt not in INVALID_REFS]
    
    def __str__(self):
        return str({self._name : self._root})

    def show(self):
        projects = dict()
        s = ["Projects contained in bank '{}':".format(self._root)]
        for b in self._repo.references:
            if b == 'refs/heads/master':
                continue
            name = b.split("/")[2]
            projects.setdefault(name, list())
            projects[name].append(b.split("/")[3])

        for pk, pv in projects.items():
            s.append("- {:<8}: {} distinct testsuite(s)".format(pk, len(pv)))
            for v in pv:
                nb_parents = 1
                cur, _ = self._repo.resolve_refish("{}/{}".format(pk, v))
                while len(cur.parents) > 0:
                    nb_parents += 1
                    cur = cur.parents[0]

                s.append("  * {}: {} runs".format(v, nb_parents))

        print("\n".join(s))

    def __del__(self):
        self.disconnect_repository()
    
    def disconnect_repository(self):
        if self._locked:
            self._locked = False
            fcntl.flock(self._lockfile, fcntl.LOCK_UN)

    def connect_repository(self):
        if self._repo is None:
            if self._new:
                try:
                    self._repo = pygit2.init_repository(
                        self._root,
                        flags=(pygit2.GIT_REPOSITORY_INIT_MKPATH |
                           pygit2.GIT_REPOSITORY_INIT_BARE |
                           pygit2.GIT_REPOSITORY_INIT_NO_REINIT),
                        mode=pygit2.GIT_REPOSITORY_INIT_SHARED_GROUP,
                        bare=True
                    )
                except Exception:
                    log.err("This path already contains a Bank!")
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
                    log.err("Unable to find a valid bank in {}".format(self._root))
            self._locked = True

        def save_to_global(self):
            global BANKS
            if self._name in BANKS:
                self._name = os.path.basename(self._root).lower()
            add_banklink(self._name, self._root)
                
    def create_test_blob(self, data):
        assert(isinstance(self._repo, pygit2.Repository))
        #assert(isinstance(data, str))

        data_hash = pygit2.hash(str(data))
        if data_hash in self._repo:
            print("save new blob : hash {}".format(data_hash))
            return self._repo[data_hash].oid
        else:
            return self._repo.create_blob(str(data))

    def insert(self, treebuild, path, obj):
        repo = self._repo
        if len(path) == 1:  # base case
            blob_obj = self.create_test_blob(obj)
            treebuild.insert(path[0], blob_obj, pygit2.GIT_FILEMODE_BLOB)
            return treebuild.write()

        subtree_name = path[0]
        tree = repo.get(treebuild.write())
        
        try:
            entry = tree[subtree_name]
            assert(entry.filemode == pygit2.GIT_FILEMODE_TREE)
            subtree = repo.get(entry.hex)
            sub_treebuild = repo.TreeBuilder(subtree)
        except KeyError:
            sub_treebuild = repo.TreeBuilder()
        
        subtree_oid = self.insert(sub_treebuild, path[1:], obj)
        treebuild.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuild.write()

    def save_test_from_json(self, jtest):
        #TODO: validate
        assert('validation' in self._config)
        test_track = jtest['id']['full_name'].split("/")
        oid = self.insert(self._rootree, test_track, jtest.to_dict())
        return oid

    def load_config_from_str(self, s):
        self._config = Dict(yaml.safe_load(s))
    
    def load_config_from_file(self, path):
        with open(os.path.join(path, "conf.yml"), 'r') as fh:
            self._config = Dict(yaml.load(fh, Loader=yaml.Loader))
        
    def save_from_buildir(self, tag, buildpath):
        self.load_config_from_file(buildpath)
        self._rootree = self._repo.TreeBuilder()

        root_subdir = os.path.join(buildpath, "test_suite")
        #TODO: need a test walkthrough (not dirs)
        for label, _ in self._config.validation.dirs.items():
            for root, _, files in os.walk(os.path.join(root_subdir, label)):
                for f in files:
                    if not (f.startswith('output-') and f.endswith('.json')):
                        continue
                    with open(os.path.join(root, f), 'r') as fh:
                        data = Dict(yaml.load(fh, Loader=yaml.Loader))
                        #TODO: validate
                    
                    for elt in data['tests']:
                        self.save_test_from_json(elt)
        self._rootree.write()
        self.finalize_snapshot(tag)

    def save_from_archive(self, tag, archivepath):
        assert(os.path.isfile(archivepath))

        with tempfile.TemporaryDirectory() as tarpath:
            tarfile.open(os.path.join(archivepath)).extractall(tarpath)
            self.save_from_buildir(tag, os.path.join(tarpath, "save_for_export"))

    def finalize_snapshot(self, tag):
        # Setup commit metadata:
        # 1. The author is the one who ran the test-suite
        # 2. The committer is submitting the archive to the bank
        # 3. the commit message is not relevant for now
        # 4. Timezone is not (yet) handled in author signature
        author = pygit2.Signature(
            name=self._config.validation.author.name,
            email=self._config.validation.author.email,
            time=int(self._config.validation.datetime.timestamp())
            )
        committer = pygit2.Signature(
            name=utils.get_current_username(),
            email=utils.get_current_usermail())
        commit_msg = "Commit message is not used (yet)"

        # a reference (lightweight branch) is tracking a whole test-suite
        # history, there are managed directly
        # TODO: compute the proper name for the current test-suite
        refname = "refs/heads/{}/{}".format(tag, self._config.validation.pf_hash)

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
            ref.name, author, committer, commit_msg,
            self._rootree.write(), parent_coid
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
            BANKS = yaml.load(f, Loader=yaml.Loader)
    except FileNotFoundError:
        # nothing to do, file may not exist
        pass
    if BANKS is None:
        BANKS = dict()


def list_banks():
    """Accessor to bank dict (outside of this module)"""
    return BANKS

def add_banklink(name, path):
    global BANKS
    BANKS[name] = path
    flush_to_disk()

def rm_banklink(name):
    global BANKS
    if name in BANKS:
        BANKS.pop(name)
        flush_to_disk()
    

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
