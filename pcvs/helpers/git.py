import getpass
import socket
import os
import time
import fcntl
from datetime import datetime
from abc import ABC, abstractmethod, abstractproperty
try:
    import pygit2
    has_pygit2 = True
except ModuleNotFoundError as e:
    import sh
    has_pygit2 = False

def elect_handler(prefix=None):
    if has_pygit2:
        git_handle = GitByAPI(prefix)
    else:
        git_handle = GitByCLI(prefix)

    return git_handle


class GitByGeneric(ABC):
    """
    Create a Git endpoint able to discuss efficiently with repositories.
    """
    def __init__(self, prefix=None, head="unknown/00000000"):
        self._path = None
        self._lck = False
        self._lockname = ""
        self._lockfd = None
        self._authname = None
        self._authmail = None
        self._commmail = None
        self._commname = None
        
        self.set_head(head)
        
        if prefix:        
            self.set_path(prefix)

    def set_path(self, prefix):
        """
        Associate a new directory to this bank.
        
        (implies locking the directory).
        """
        assert(not self._lck)
        self._path = prefix
        self._lck = False
        self._lockname = os.path.join(prefix, ".pcvs.lock")
        
    def _trylock(self):
        """
        Lock the current repository (NON-BLOCKING)
        """
        if not self._lockfd:
            self._lockfd = open(self._lockname, "w+")
            self._lck = False
            
        try:
            fcntl.flock(self._lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lck = True
        except BlockingIOError:
            self._lck = False
        return self._lck
        
    def _lock(self):
        """
        Lock the current reposiotry (BLOCKING)
        """
        while not self._lck:
            if not self._trylock():
                time.sleep(1)
    
    def _unlock(self):
        """
        Unlock the current repository.
        """
        if self._lck:
            self._lck = False
            fcntl.flock(self._lockfd, fcntl.LOCK_UN)
    
    def _is_locked(self):
        """Locked repo checker"""
        return self._lck is True
            
    def set_identity(self, authname, authmail, commname, commmail):
        """Identities to be used if a commit is created."""
        self._authname = authname if authname else get_current_username()
        self._authmail = authmail if authmail else get_current_usermail()
        self._commname = commname if commname else get_current_username()
        self._commmail = commmail if commmail else get_current_usermail()
    
    def get_head(self, prefix):
        """Get the current HEAD (used when no default)"""
        return self._head
    
    def set_head(self, new_head):
        """Move the repo HEAD (used when no default ref is provided)"""
        self._head = new_head
   
    @abstractproperty
    def branches(self):
        """
        Returns the list of available local branche names from this repo.
        """
        pass
    
    @abstractmethod
    def open(self):
        """Open a new directory. Also lock to avoid races."""
        pass
    @abstractmethod
    def is_open(self):
        """Is the directory currently open ?"""
        pass
    @abstractmethod
    def close(self):
        """Unlock the repository."""
        pass
    @abstractmethod
    def get_tree(self, tree, prefix):
        """Retrieve data associated with a given prefix. A tree can used
        to set which ref should be used.
        
        :param[in] tree: the ref from where get the data
        :param[in] prefix: the unique prefix associated with data
        """
        pass
    
    @abstractmethod
    def insert_tree(self, prefix, data):
        """Create a new tree mapping a prefix filled with 'data'.
        
        :param[in] prefix: the prefix under Git tree.
        :param[in] data: the data to store.
        """
        pass
    @abstractmethod
    def diff_tree(self, prefix, src_rev, dst_rev):
        """
        Compare & return the list of patches 
        """
        pass
    @abstractmethod
    def list_commits(self, rev, since, until): pass
    @abstractmethod
    def commit(self, id): pass
    @abstractmethod
    def revparse(self, rev): pass
    @abstractmethod
    def iterate_over(self, ref): pass
    @abstractmethod
    def list_files(self, rev): pass
    
    def _set_or_head(self, rev):
        return rev if rev else self._head


class GitByAPI(GitByGeneric):
    """
    Manage repository through a third-party Python module.
    
    Currently, this work is based on pygit2.
    """
    def __init__(self, prefix=None):
        super().__init__(prefix)
        self._repo = None

    def open(self, bare=True):
        assert(not os.path.isfile(self._path))
        if not os.path.isdir(self._path) or len(os.listdir(self._path)) == 0:
            if not self._is_locked():
                self._repo = pygit2.init_repository(
                            self._path,
                            flags=(pygit2.GIT_REPOSITORY_INIT_MKPATH |
                                pygit2.GIT_REPOSITORY_INIT_NO_REINIT),
                            mode=pygit2.GIT_REPOSITORY_INIT_SHARED_GROUP,
                            bare=bare
                        )
                self._lock()
        else:
            rep = pygit2.discover_repository(self._path)
            if rep:
                self._repo = pygit2.Repository(rep)
                self._lock()
        
        self._rootree = None

    def is_open(self):
        return self._repo is not None

    def close(self):
        self._unlock()

    @property
    def branches(self):
        assert(self._repo)
        return self._repo.branches.local
    
    def revparse(self, name):
        assert(self._repo)
        if isinstance(name, str):
            return self._repo.resolve_refish(name)[0]
        elif isinstance(name, pygit2.Branch):
            return name.peel()
        return name
    
    def get_blob(self, rev=None, prefix=""):
        tree = self.get_tree(rev, prefix)
        if not isinstance(tree, pygit2.Blob):
            assert(0)
        
        return tree.data.decode()
        

    def get_tree(self, rev=None, prefix=""):
        rev = self._set_or_head(rev)
        tree = self._repo.revparse_single(rev).tree
        
        if prefix:
            return self._get_tree(prefix.split("/"), tree)
        else:
            return tree
        
    def _get_tree(self, chain, tree=None):
        if len(chain) <= 0:
            return tree
        else:
            subtree = None
            for i in tree:
                if chain[0] == i.name:
                    subtree = i
                    break
            return self._get_tree(chain[1:], subtree)

    def get_info(self, obj):
        obj = self.revparse(obj)
        assert(isinstance(obj, pygit2.Object))
        
        return {
            'date': datetime.fromtimestamp(obj.author.time),
            'author': obj.author.name,
            'authmail': obj.author.email,
            'metadata': [],
        }

    def iterate_over(self, rev=None):
        rev = self._set_or_head(rev)
        rev = self.revparse(rev)
        assert(isinstance(rev, pygit2.Object))
        
        for elt in self._repo.walk(rev.oid, pygit2.GIT_SORT_REVERSE):
            yield elt

    def insert_tree(self, prefix, data):
        if not self._rootree:
            self._rootree = self._repo.TreeBuilder()
        self.__insert_path(self._rootree, prefix.split('/'), data)

    def list_files(self, rev=None, prefix=None):
        if not prefix:
            prefix = ""
        
        rev = self._set_or_head(rev)
        rev = self.revparse(rev)
        assert(isinstance(rev, pygit2.Commit))
        
        tree = rev.tree
        return [e.old_file.path for e in tree.diff_to_tree().deltas]
    
    def diff_tree(self, prefix=None, src_rev=None, dst_rev=None):
        src_rev = self._set_or_head(src_rev)
        src_rev = self.revparse(src_rev)
        
        assert(isinstance(src_rev, pygit2.Object))
        if dst_rev:
            dst_rev = self._set_or_head(dst_rev)
            dst_rev = self.revparse(dst_rev)
            assert(isinstance(dst_rev, pygit2.Object))
            
            diff = src_rev.diff_to_tree(dst_rev)
        else:
            diff = src_rev.diff_to_tree()
    
    def list_commits(self, rev=None, since=None, until=None):
        res = []
        rev = self._set_or_head(rev)
        rev = self.revparse(rev)
        
        if since is None:
            since = datetime.now().timestamp()
            
        if until is None:
            until = 0
        for c in self.iterate_over(rev):
            if c.commit_time <= since and c.commit_time >= until:
                res.append(c.short_id)
        return res
        
    def commit(self, msg="No data", timestamp=None):
        assert(self._repo)
        
        if not timestamp:
            timestamp = int(datetime.now().timestamp())

        if self._authname and self._authmail:
            author = pygit2.Signature(name=self._authname,
                                  email=self._authmail,
                                  time=timestamp)
        else:
            author = self._repo.default_signature
        
        if self._commname and self._commmail:
            committer = pygit2.Signature(name=self._commname,
                                     email=self._commname,
                                     time=timestamp)
        else:
            committer = self._repo.default_signature

        parent_ref = None
        parent = []
        
        if self._head in self._repo.branches:
            parent, ref = self._repo.resolve_refish(self._head)
            parent = [parent.oid]
            parent_ref = ref.name
            
        coid = self._repo.create_commit(
            parent_ref,
            author,
            committer,
            msg,
            self._rootree.write(),
            parent
        )
        
        if parent_ref is None:
            self._repo.branches.local.create(self._head, self._repo.get(coid))
            
        self._rootree = None
            
                    
    def __insert_path(self, treebuild, path, data: any):
        """Associate an object to a given tag (=path).

        The result is stored into the parent subtree (treebuild). The path is an
        array of subrefixes, identifying the subtree where the object will
        be stored under the bank. This function associates the path & the object
        together, write the result in the parent and returns its Oid.

        This function is called recursively to build the whole tree. The stop
        condition is when the function reaches the file (=basename), which
        create the real blob object.

        :param treebuild: the parent Oid where this association will be stored
        :type treebuild: :class:`Pygit2.TreeBuilder`
        :param path: the subpath where to store the object
        :type path: list of str
        :param obj: the actual data to store
        :type obj: any
        :return: the actual parent id
        :rtype: :class:`Pygit2.Oid`
        """
        repo = self._repo

        # the basename is reached -> generate the blob and return the parend oid
        if len(path) == 1:
            data_hash = pygit2.hash(str(data))
            if data_hash in self._repo:
                data_obj = self._repo[data_hash].oid
            else:
                data_obj = self._repo.create_blob(str(data))
            treebuild.insert(path[0], data_obj, pygit2.GIT_FILEMODE_BLOB)
            return treebuild.write()

        # otherwise, determine where the current subdir is going
        subtree_name = path[0]
        tree = repo.get(treebuild.write())

        try:
            # check if the subdir already exist in this bank subtree
            entry = tree[subtree_name]
            assert(entry.filemode == pygit2.GIT_FILEMODE_TREE)
            subtree = repo.get(entry.hex)
            # YES it is found -> reuse this subtree
            sub_treebuild = repo.TreeBuilder(subtree)
        except KeyError:
            # NOPE: first time adding a resource to this subtree
            # create a new one
            sub_treebuild = repo.TreeBuilder()

        # recursive call, as we didn't reach the subtree bottom
        subtree_oid = self.__insert_path(sub_treebuild, path[1:], data)
        # Pygit2 insert, to build the actual intemediate node
        treebuild.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuild.write()
        

class GitByCLI(GitByGeneric):
    """
    Git endpoint ot manipulate a repository through basic CLI.
    
    Currently relying on the `sh` module.
    """
    def __init__(self, prefix=""):
        super().__init__(prefix)
        self._git = None
        self._rootree = None
        
    @property
    def branches(self):
        array = self._git('for-each-ref', 'refs/heads/').strip().split("\n")
        return [elt.split('\t')[-1].replace("refs/heads/", "") for elt in array]
    
    def iterate_over(self, ref):
        res = []
        for elt in self._git('rev-list', '--reverse', ref).strip().split("\n"):
            res.append(elt)
        return res
        
    def open(self):
        if not os.path.isdir(self._path):
            os.makedirs(self._path)
        
        self._lock()
        self._git = sh.git.bake(_cwd=self._path)
        
        if not os.path.isfile(os.path.join(self._path, "HEAD")):
            self._git.init("--bare")
        
    def is_open(self):
        return self._is_locked()

    def close(self):
        self._git = None
        self._unlock()
        
    def revparse(self, name):
        return self._git("rev-parse", name).strip()
    
    def _create_blob(self, name, data):
        oid = ""
        oid = self._git('hash-object', "--stdin", "-w", _in=str(data)).strip()
        return (oid, "100644 blob {}\t{}".format(oid, name))
    
    def _create_tree(self, name, children):
        array = []
        for k, v in children.items():
            if isinstance(v, dict):
                array.append(self._create_tree(k, v)[1])
            else:
                array.append(self._create_blob(k, v)[1])

        oid = self._git.mktree(_in="\n".join(array)).strip()
        return (oid, "040000 tree {}\t{}".format(oid, name))
        
    def insert_tree(self, prefix, data):
        if not self._rootree:
            self._rootree = dict()
            
        self._insert_path(self._rootree, prefix.split("/"), data)
    
    def get_tree(self, tree=None, prefix=""):
        oid=None
        if not tree:
            tree = self._head
        try:
            self._git("rev-parse", "{}:{}".format(tree, prefix), _out=oid)
        except sh.ErrorReturnCode:
            oid = None
        return oid

    def _insert_path(self, subtree, subprefix, data):
        if len(subprefix) == 1:
            subtree[subprefix[0]] = data
        else:
            current = subprefix[0]
            subtree.setdefault(current, {})
            self._insert_path(subtree[current], subprefix[1:], data)
        
    def commit(self, msg="VOID", timestamp=None):
        
        oid, _ = self._create_tree("root", self._rootree)
        parent = ""
        if self._head in self.branches:
            commit_id = self._git("commit-tree", oid, 
                  "-m '{}'".format(msg),
                  "-p {}".format(self._head)
            ).strip()
        else:
            commit_id = self._git("commit-tree", oid, 
                  "-m '{}'".format(msg),
            ).strip()

        self._git.push(".", "{}:refs/heads/{}".format(commit_id, self._head))
        
        self._rootree = None

    def list_files(self, prefix):
        if not prefix:
            prefix = ""
        return [self._git('ls-files', prefix).strip().split("\n")]

    def list_commits(self, rev=None, since="", until=""):
        rev = self._set_or_head(rev)
        if since:
            since = "--since={}".format(since)
        if until:
            until = "--until={}".format(until)
        
        return [self._git("log", "--no-pager", rev, since, until, "--pretty=format:'%H'").strip()]

    def diff_tree(self, prefix=None, src_rev=None, dst_rev=None):
        
        if not dst_rev:
            return None
        
        src_rev = self._set_or_head(src_rev)
        src_rev = self.revparse(src_rev)
        
        return self._git('diff-tree', src_rev, dst_rev).strip()
 

def request_git_attr(k) -> str:
    """Get a git configuration.

    :param k: parameter to get
    :type k: str
    :return: a git configuration
    :rtype: str
    """
    try:
        git_conf = dict()
        # TODO: not only look for user config
        if has_pygit2:
            git_conf = pygit2.Config.get_global_config()
        else:
            git_conf[k] = sh.git.config('--get', k).strip()
        if k in git_conf:
            return git_conf[k]
    except IOError:
        # to user config
        pass
    return None


def generate_data_hash(data) -> str:
    """Hash data with git protocol.

    :param data: data to hash
    :type data: str
    :return: hashed data
    :rtype: str
    """
    if has_pygit2:
        return str(pygit2.hash(data))
    else:
        return hash(data)


def get_current_username() -> str:
    """Get the git username.

    :return: git username
    :rtype: str
    """
    u = request_git_attr('user.name')
    if u is None:
        return getpass.getuser()
    else:
        return u


def get_current_usermail():
    """Get the git user mail.

    :return: git user mail
    :rtype: str
    """
    m = request_git_attr('user.email')
    if m is None:
        return "{}@{}".format(get_current_username(), socket.getfqdn())
    else:
        return m
