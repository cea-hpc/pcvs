import getpass
import socket
import os
import time
import fcntl
import sh
from datetime import datetime
from pcvs.helpers.system import MetaDict

try:
    import pygit2
    has_pygit2 = True
except ModuleNotFoundError as e:
    has_pygit2 = False

def elect_handler(prefix=None):
    if has_pygit2:
        git_handle = GitByAPI(prefix)
    else:
        git_handle = GitByCLI(prefix)

    return git_handle
    
class GitByGeneric:
    def __init__(self, prefix=None):
        self._path = None
        self._lck = False
        self._lockname = ""
        self._lockfd = None
        self._authname = None
        self._authmail = None
        self._commmail = None
        self._commname = None
        
        if prefix:        
            self.set_path(prefix)

    
    def set_path(self, prefix):
        assert(not self._lck)
        self._path = prefix
        self._lck = False
        self._lockname = os.path.join(prefix, ".pcvs.lock")
        
    def _trylock(self):
        
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
        while not self._lck:
            if not self._trylock():
                time.sleep(1)
    
    def _unlock(self):
        if self._lck:
            self._lck = False
            fcntl.flock(self._lockfd, fcntl.LOCK_UN)
    
    def _is_locked(self):
        return self._lck is True
            
    def set_identity(self, authname, authmail, commname, commmail):
        self._authname = authname if authname else get_current_username()
        self._authmail = authmail if authmail else get_current_usermail()
        self._commname = commname if commname else get_current_username()
        self._commmail = commmail if commmail else get_current_usermail()
    
    @property
    def refs(self): pass
    @property
    def branches(self): pass
    def open(self): pass
    def is_open(self): pass
    def close(self): pass
    def get_tree(self, prefix): pass
    def get_head(self, prefix): pass
    def change_branch(self, branchname): pass
    def insert_tree(self, prefix, data): pass
    def commit(self, id): pass

    
class GitByAPI(GitByGeneric):
    def __init__(self, prefix=None):
        super().__init__(prefix)
        self._repo = None
            
    def open(self, bare=True):
        assert(not os.path.isfile(self._path))
        if not os.path.isdir(self._path):
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
        return self._repo is True

    def close(self):
        self._unlock()

    @property
    def refs(self):
        assert(self._repo)
        return self._repo.references
    
    @property
    def branches(self):
        assert(self._repo)
        return self._repo.branches.local

    def get_tree(self, prefix):
        pass

    def get_head(self, prefix):
        pass

    def change_branch(self, branchname):
        pass

    def insert_tree(self, prefix, data):
        if not self._rootree:
            self._rootree = self._repo.TreeBuilder()
        self.__insert_path(self._rootree, prefix.split('/'), data)

    def commit(self, head_name, msg="No data", timestamp=None):
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

        parent_ref = MetaDict({'name': None})
        parent = []
        
        if head_name in self._repo.branches:
            parent, parent_ref = self._repo.resolve_refish(head_name)
            parent = [parent.oid]
            
        coid = self._repo.create_commit(
            parent_ref.name,
            author,
            committer,
            msg,
            self._rootree.write(),
            parent
        )
        
        if parent_ref.name is None:
            self._repo.branches.local.create(head_name, self._repo.get(coid))
            
        self._rootree = None
            
                    
    def __insert_path(self, treebuild, path, data: any) -> pygit2.Object:
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
    
    def __init__(self, prefix=""):
        super().__init__(prefix)
        self._git = None
        
    
    @property
    def refs(self): pass
    @property
    def branches(self): pass
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
        
    def get_tree(self, prefix): pass
    def get_head(self, prefix): pass
    def change_branch(self, branchname): pass
    def insert_tree(self, prefix, data): pass
        self._git
    def commit(self, id): pass

    


def request_git_attr(k) -> str:
    """Get a git configuration.

    :param k: parameter to get
    :type k: str
    :return: a git configuration
    :rtype: str
    """
    try:
        # TODO: not only look for user config
        git_conf = pygit2.Config.get_global_config()
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
    return str(pygit2.hash(data))


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
