import getpass
import hashlib
import os
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import Any
from typing import Iterable

import sh
from typing_extensions import Self

from pcvs.helpers import utils
from pcvs.helpers.exceptions import GitException

try:
    import pygit2

    HAS_PYGIT2 = True
except ModuleNotFoundError:
    HAS_PYGIT2 = False


class Reference:
    """Maps an object which can be "pointed" (as a Git semantic). It can usually
    be used to refer a commit, a simple hash or a branch."""

    def __init__(self, repo):
        self._repo = repo

    @property
    def repo(self):
        """Getter to the repo this reference comes from."""
        return self._repo


class Branch(Reference):
    """Maps to a regular Git branch."""

    def __init__(self, repo, name: str = "master"):
        super().__init__(repo)
        self._name = name

    @property
    def name(self) -> str:
        return self._name


class Commit(Reference):
    """Maps to a regular Git commit"""

    def __init__(self, repo, obj, metadata: dict[str, Any] | None = None):
        super().__init__(repo)
        if metadata is None:
            metadata = {}
        self.cid = obj
        self.meta = metadata

    def get_info(self) -> dict[str, Any]:
        """
        Return commit metadata stored as a dict.

        It may contains extra infos compared to what a commit usually contains

        :return: The data attached to the commit object when initialized.
        """
        return self.meta


class Tree(Reference):
    """Maps to a git-lowlevel Tree object"""

    def __init__(self, repo, tid, prefix="", children=None):
        super().__init__(repo)
        if children is None:
            children = []
        self.tid = tid
        self.prefix = prefix
        self.children = children

    @classmethod
    def as_root(cls, repo: Any, hdl: Any, children: list | None = None) -> Self:
        """Create a Tree and attach it with the git-specific handler (if any)

        :param repo: the repo handle
        :param hdl: the git-specific root handle
        :param children: Any prebuild children for this root node
        :return: the created Tree object
        """
        if children is None:
            children = []
        cls.hdl = hdl  # type: ignore
        return cls(repo=repo, tid=None, prefix="", children=children)


class Blob(Tree):
    """Maps a Git 'blob' object, dedicated to hold data ("leaves" in Git trees)"""

    def __init__(self, repo, tid, prefix: str = "", data: bytes = b""):
        super().__init__(repo, tid, prefix, children=[])
        self.data: bytes = data

    def __str__(self) -> str:
        """
        Stringify data contained in blob.

        :returns: the decoded data
        """
        return self.data.decode()


class GitByGeneric(ABC):
    """
    Create a Git endpoint able to discuss efficiently with repositories.

    This base class serves abstract methods to be implemented to create a new
    derived class. Currently are provided:
    - GitByAPI: relies on python module pygit2 (requires libgit2)
    - GitByCLI: based on regular Git program invocations (require git program)
    """

    def __init__(self, prefix=None, head="unknown/00000000"):
        self._path = None
        self._lockname = ""
        self._lockfd = None
        self._authname = None
        self._authmail = None
        self._commmail = None
        self._commname = None

        self.set_head(head)

        if prefix:
            self.set_path(prefix)

        self.set_identity(None, None, None, None)

    @abstractmethod
    def open(self, bare: bool = True) -> None:
        """
        Open the repo, with appropriate method.

        :param bare: true by default, manage or bare repo.
        """

    def set_path(self, prefix: str):
        """
        Associate a new directory to this bank.

        :param prefix: the prefix locating the Git repo
        """
        self._path = prefix
        self._lockname = os.path.join(prefix, ".pcvs")

    def _trylock(self) -> bool:
        """
        Lock the current repository (NON-BLOCKING)

        :return: true if the file is locked, false otherwise
        """
        return utils.trylock_file(self._lockname)

    def _lock(self) -> bool:
        """
        Lock the current repository (BLOCKING)

        :return: true if the file is locked, false otherwise
        """
        return utils.lock_file(self._lockname)

    def _unlock(self):
        """
        Unlock the current repository.
        """
        utils.unlock_file(self._lockname)

    def _is_locked(self) -> bool:
        """Locked repo checker

        :return: true if the file is locked, false otherwise
        """
        return utils.is_locked(self._lockname)

    def set_identity(
        self, authname: str | None, authmail: str | None, commname: str | None, commmail: str | None
    ) -> None:
        """Identities to be used if a commit is created.

        :param authname: author's name
        :param authmail: author's email
        :param commname: Committer's name
        :param commmail: Committer's email
        """
        self._authname = authname if authname else get_current_username()
        self._authmail = authmail if authmail else get_current_usermail()
        self._commname = commname if commname else get_current_username()
        self._commmail = commmail if commmail else get_current_usermail()

    def get_head(self) -> Branch:
        """Get the current repo's HEAD (used when no default)

        :returns: a ref to the HEAD as a branch
        """
        return self._head

    def set_head(self, branch_name: str) -> None:
        """Move the repo HEAD (used when no default ref is provided)"""
        self._head = Branch(self, branch_name)

    @abstractmethod
    def branches(self) -> list[Branch]:
        """
        Returns the list of available local branch names from this repo.

        This is an abstract function as its behavior depends on derived classes.
        """

    @abstractmethod
    def new_branch(self, name: str, cid: Reference | None = None) -> Branch:
        """
        Create a new branch.
        """

    @abstractmethod
    def get_branch_from_str(self, name: str) -> Branch | None:
        """
        Return the branch with name 'name'.
        """

    @abstractmethod
    def set_branch(self, branch: Branch, commit: Reference) -> None:
        """
        Set branch.
        """

    @abstractmethod
    def is_open(self) -> bool:
        """Is the directory currently open ?"""

    @abstractmethod
    def close(self) -> None:
        """Unlock the repository."""

    @abstractmethod
    def get_tree(self, tree: Reference | None = None, prefix: str = "") -> Blob | Tree | None:
        """
        Retrieve data associated with a given prefix. A tree can used
        to set which ref should be used.

        :param tree: the ref from where get the data
        :param prefix: the unique prefix associated with data
        """

    @abstractmethod
    def insert_tree(self, prefix: str, data: Any, root: Tree | None = None) -> Tree:
        """
        Create a new tree mapping a prefix filled with 'data'.

        :param prefix: the prefix under Git tree.
        :param data: the data to store.
        :param root: the root tree  to insert the data in.
        """

    @abstractmethod
    def diff_tree(self, prefix: str, src_rev: Reference, dst_rev: Reference):
        """
        Compare & return the list of patches
        """

    @abstractmethod
    def list_commits(
        self,
        rev: Reference | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Commit]:
        """List past commits finishing with 'rev'.

        The list can be shrunk with a start & end

        :param rev: the revision to extract commit from
        :param since: the oldest commit should be newer than this date
        :param until: the newest commit should be older than this date
        """

    @abstractmethod
    def do_commit(
        self,
        tree: Tree,
        msg: str = "No data",
        timestamp: int | None = None,
        parent: Reference | None = None,
        orphan: bool = False,
    ) -> Commit:
        """Create a commit from changes.

        :param tree: the changes tree to store as a commit
        :param msg: the commit msg
        :param timestamp: a commit date (current if not provided)
        :param parent: the parent commit
        :param orphan: flag to create a dangling commit (=no-parent)
        """

    @abstractmethod
    def revparse(self, rev: Reference) -> Commit:
        """
        Convert a revision (tag, branch, commit) to a regular reference.

        :param rev: Reference
        """

    @abstractmethod
    def iterate_over(self, ref: Reference) -> Iterable[Commit]:
        """starting from the ref, iterate references backwards (from newest to
        oldest).

        :param ref: the starting point
        """

    @abstractmethod
    def list_files(self, rev: Reference | None = None, prefix: str = "") -> list[str]:
        """For a given revision, list files (not only changed ones).

        :param rev: the reference
        :param prefix: the prefix
        """

    @abstractmethod
    def gc(self):
        """Run the garbage collector"""

    @abstractmethod
    def get_parents(self, ref: Reference) -> list[Commit]:
        """Retrieve parents for a given ref.

        This method is not a part of a Reference object as the approach changes
        depending on the Git method used (lazy resolution).

        :param ref: the revision
        """

    def _set_or_head(self, rev: Reference | None) -> Reference:
        """
        Return a valid revision to be used

        If rev is not set, return the default HEAD repo.

        :param rev: the revision to use or replace if not set
        :return: The reference or head.
        """
        return rev if rev else self._head


class GitByAPI(GitByGeneric):
    """
    Manage repository through a third-party Python module.

    Currently, this work is based on pygit2.
    """

    def __init__(self, prefix=None):
        super().__init__(prefix)
        self._repo = None

    def open(self, bare: bool = True) -> None:
        assert not os.path.isfile(self._path)
        if not os.path.isdir(self._path) or len(os.listdir(self._path)) == 0:
            if not self._is_locked():
                self._repo = pygit2.init_repository(
                    self._path,
                    flags=(
                        pygit2.GIT_REPOSITORY_INIT_MKPATH | pygit2.GIT_REPOSITORY_INIT_NO_REINIT
                    ),
                    mode=pygit2.GIT_REPOSITORY_INIT_SHARED_GROUP,
                    bare=bare,
                )
                self._lock()
        else:
            rep = pygit2.discover_repository(self._path)
            if rep:
                self._repo = pygit2.Repository(rep)
                self._lock()

    def get_branch_from_str(self, name: str) -> Branch | None:
        for b in self.branches():
            if name == b.name:
                return b
        return None

    def is_open(self) -> bool:
        return self._is_locked()

    def close(self) -> None:
        self._unlock()

    def __obj_to_commit(self, obj):
        assert isinstance(obj, pygit2.Commit)
        return Commit(
            repo=self._repo,
            obj=obj,
            metadata={
                "obj": obj,
                "date": datetime.fromtimestamp(obj.author.time),
                "author": obj.author.name,
                "authmail": obj.author.email,
                "message": obj.message,
                "parents": obj.parents,
            },
        )

    def branches(self) -> list[Branch]:
        assert self._repo
        return [Branch(self, e) for e in self._repo.branches.local]

    def new_branch(self, name: str, cid: Reference | None = None) -> Branch:
        assert name is not None
        if cid is None:
            real_cid = self.revparse(Branch(self, name="master")).cid
        else:
            real_cid = self.revparse(cid).cid

        assert name not in self._repo.branches.local
        self._repo.branches.local.create(name, real_cid)
        return Branch(self, name=name)

    def set_branch(self, branch: Branch, commit: Reference) -> None:
        assert isinstance(commit, Reference)
        assert isinstance(branch, Branch)

        pygit_obj = self.revparse(commit).cid.oid
        ref = "refs/heads/{}".format(branch.name)
        if ref in self._repo.references:
            self._repo.references.delete(branch.name)
        self._repo.references.create("refs/heads/{}".format(branch.name), pygit_obj)

    def revparse(self, rev: Reference) -> Commit:
        assert self._repo
        assert isinstance(rev, Reference)

        if isinstance(rev, Commit):
            return rev

        o = self._repo.revparse_single(rev.name)
        return self.__obj_to_commit(o)

    def get_tree(self, tree: Reference | Any | None = None, prefix: str = "") -> Blob | Tree | None:
        assert not tree or isinstance(tree, Reference)
        rev = self._set_or_head(tree)

        tree = None
        if isinstance(rev, Branch):
            assert self._repo is not None
            tree = self._repo.revparse_single(rev.name).tree
        elif isinstance(rev, Commit):
            tree = rev.cid.tree

        if prefix:
            tid = self._get_tree(prefix.split("/"), tree)
        else:
            tid = tree

        if tid is None:
            return None
        if isinstance(tid, pygit2.Blob):
            return Blob(self, tid, prefix, tid.data)
        return Tree(self, tid, prefix)

    def _get_tree(self, chain, tree=None):
        if len(chain) <= 0:
            return tree
        subtree = None
        for file in tree:
            if chain[0] == file.name:
                subtree = file
                break
        else:
            return None  # file you are looking for does not exist in this git
        return self._get_tree(chain[1:], subtree)

    def iterate_over(self, ref: Reference) -> Iterable[Commit]:
        assert isinstance(ref, Reference)
        rev = self._set_or_head(ref)
        rev = self.revparse(rev)
        assert isinstance(rev, Commit)
        pygit_obj = rev.cid

        for o in self._repo.walk(pygit_obj.oid, pygit2.GIT_SORT_REVERSE):
            yield self.__obj_to_commit(o)

    def list_files(self, rev: Reference | None = None, prefix: str = "") -> list[str]:
        assert not rev or isinstance(rev, Reference)
        rev = self._set_or_head(rev)
        rev = self.revparse(rev)
        assert isinstance(rev, Commit)
        tree = rev.cid.tree
        return [
            e.old_file.path
            for e in tree.diff_to_tree().deltas
            if e.old_file.path.startswith(prefix)
        ]

    def diff_tree(self, prefix=None, src_rev=None, dst_rev=None):
        src_rev = self._set_or_head(src_rev)
        src_rev = self.revparse(src_rev)

        assert isinstance(src_rev, pygit2.Object)
        if dst_rev:
            dst_rev = self._set_or_head(dst_rev)
            dst_rev = self.revparse(dst_rev)
            assert isinstance(dst_rev, pygit2.Object)

    def list_commits(
        self,
        rev: Reference | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Commit]:
        res = []
        assert not rev or isinstance(rev, Reference)

        if since is None:
            since = datetime.now()

        if until is None:
            until = datetime.fromtimestamp(0)

        for c in self.iterate_over(rev):
            pygit_obj = c.cid
            if (
                pygit_obj.commit_time <= since.timestamp()
                and pygit_obj.commit_time >= until.timestamp()
            ):
                res.append(self.__obj_to_commit(pygit_obj))
        return res

    def do_commit(
        self,
        tree: Tree,
        msg: str = "No data",
        timestamp: int | None = None,
        parent: Reference | None = None,
        orphan: bool = False,
    ) -> Commit:
        assert self._repo
        assert isinstance(tree, Tree)
        assert not parent or isinstance(parent, Reference)

        if not timestamp:
            timestamp = int(datetime.now().timestamp())

        author = pygit2.Signature(name=self._authname, email=self._authmail, time=timestamp)
        committer = pygit2.Signature(name=self._commname, email=self._commname, time=timestamp)

        parents = []
        update_ref = None
        if not orphan:
            parent = self._set_or_head(parent)
            if isinstance(parent, Branch):
                update_ref = "refs/heads/{}".format(parent.name)
                parents = [self.revparse(parent).cid.oid]
            elif isinstance(parent, Commit):
                update_ref = None
                parents = [parent.cid.oid]
            else:
                raise GitException.BadEntryError(
                    reason="Parent is unknown", dbg_info={"ref": parent}
                )

        coid = self._repo.create_commit(
            update_ref, author, committer, msg, tree.hdl.write(), parents
        )
        ci = self._repo.get(coid)
        return self.__obj_to_commit(ci)

    def insert_tree(self, prefix: str, data: Any, root: Tree | None = None) -> Tree:
        if not root:
            root = Tree.as_root(self._repo, self._repo.TreeBuilder())

        pygit_obj = root.hdl
        self.__insert_path(pygit_obj, prefix.split("/"), data)
        # root.tid = pygit_obj.

        return root

    def __insert_path(
        self, treebuild: pygit2.TreeBuilder, path: list[str], data: Any
    ) -> pygit2.Oid:
        """Associate an object to a given tag (=path).

        The result is stored into the parent subtree (treebuild). The path is an
        array of subrefixes, identifying the subtree where the object will
        be stored under the bank. This function associates the path & the object
        together, write the result in the parent and returns its Oid.

        This function is called recursively to build the whole tree. The stop
        condition is when the function reaches the file (=basename), which
        create the real blob object.

        :param treebuild: the parent Oid where this association will be stored
        :param path: the subpath where to store the object
        :param data: the actual data to store
        :return: the actual parent id
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
            assert entry.filemode == pygit2.GIT_FILEMODE_TREE
            subtree = repo.get(entry.hex)
            # YES it is found -> reuse this subtree
            sub_treebuild = repo.TreeBuilder(subtree)
        except KeyError:
            # NOPE: first time adding a resource to this subtree
            # create a new one
            sub_treebuild = repo.TreeBuilder()

        # recursive call, as we didn't reach the subtree bottom
        subtree_oid = self.__insert_path(sub_treebuild, path[1:], data)
        # Pygit2 insert, to build the actual intermediate node
        treebuild.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuild.write()

    def gc(self):
        hdl = sh.git.bake(_cwd=self._path)
        hdl.gc()

    def get_parents(self, ref):
        assert isinstance(ref, Reference)

        ref = self._set_or_head(ref)
        ref = self.revparse(ref)

        return [self.__obj_to_commit(p) for p in ref.meta["parents"]]


class GitByCLI(GitByGeneric):
    """
    Git endpoint to manipulate a repository through basic CLI.

    Currently relying on the `sh` module.
    """

    def __init__(self, prefix=""):
        super().__init__(prefix)
        self._git = None

    def branches(self) -> list[Branch]:
        array = self._git("for-each-ref", "refs/heads/").strip().split("\n")
        return [Branch(self, elt.split("\t")[-1].replace("refs/heads/", "")) for elt in array]

    def iterate_over(self, ref: Reference) -> Iterable[Commit]:
        assert isinstance(ref, Reference)
        for elt in self._git("rev-list", "--reverse", ref).strip().split("\n"):
            yield Commit(repo=self, obj=elt)

    def open(self, bare: bool = True) -> None:
        if not os.path.isdir(self._path):
            os.makedirs(self._path)

        self._lock()
        self._git = sh.git.bake(_cwd=self._path)

        if not os.path.isfile(os.path.join(self._path, "HEAD")):
            self._git.init("--bare")

    def is_open(self) -> bool:
        return self._is_locked()

    def close(self) -> None:
        self._git = None
        self._unlock()

    def revparse(self, rev: Reference) -> Commit:
        assert isinstance(rev, Reference)
        if isinstance(rev, Commit):
            return rev
        return Commit(repo=self, obj=self._git("rev-parse", rev.name).strip())

    def _create_blob(self, name, data):
        oid = ""
        oid = self._git("hash-object", "--stdin", "-w", _in=str(data)).strip()
        return (oid, "100644 blob {}\t{}".format(oid, name))

    def __valid_object(self, hashid):
        try:
            self._git("cat-file", "-e", hashid)
        except Exception:
            return False
        return True

    def _insert_path(self, treebuild, path, data):
        assert isinstance(treebuild, Tree)

        assert len(path) == 1

        data_hash = generate_data_hash(str(data))
        if not self.__valid_object(data_hash):
            check = self._create_blob(path, data)
            assert check == data_hash
        treebuild.children.append(data_hash)
        return data_hash

    def _create_tree(self, name, children):
        array = []
        for k, v in children.items():
            if isinstance(v, dict):
                array.append(self._create_tree(k, v)[1])
            else:
                array.append(self._create_blob(k, v)[1])

        oid = self._git.mktree(_in="\n".join(array)).strip()
        return (oid, "040000 tree {}\t{}".format(oid, name))

    def insert_tree(self, prefix: str, data: Any, root: Tree | None = None) -> Tree:
        if not root:
            root = Tree.as_root(self, None)

        raise NotImplementedError()
        # self._insert_path(root, prefix.split("/"), data)

        # return root

    def get_tree(self, tree: Reference | None = None, prefix: str = "") -> Blob | Tree | None:
        oid = None
        assert not tree or isinstance(tree, Reference)
        rev = self._set_or_head(tree)

        try:
            self._git("rev-parse", "{}:{}".format(rev, prefix), _out=oid)
        except sh.ErrorReturnCode:
            oid = None

        if self._git("cat-file", "-t", oid) == "blob":
            data = self._git("cat-file", "-p", oid).strip()
            return Blob(self, oid, prefix, data)
        return Tree(self, oid, prefix)

    def __obj_to_commit(self, cid):
        s = self.__commit_info_getter("%at:%an:%ae", "-1", cid).split(":")
        msg = self.__commit_info_getter("%B", "-1", cid)
        return Commit(
            repo=self,
            obj=cid,
            metadata={
                "obj": cid,
                "date": datetime.fromtimestamp(int(s[0])),
                "author": s[1],
                "authmail": s[2],
                "message": msg,
            },
        )

    def do_commit(
        self,
        tree: Tree,
        msg: str = "No data",
        timestamp: int | None = None,
        parent: Reference | None = None,
        orphan: bool = False,
    ) -> Commit:
        assert not parent or isinstance(parent, Reference)
        assert isinstance(tree, Tree)
        # if this commit should have parents
        if not orphan:

            parent = self._set_or_head(parent)
            parents = self.revparse(parent)
            commit_id = self._git(
                "commit-tree", tree, "-m '{}'".format(msg), "-p {}".format(parents.cid)
            ).strip()
            if isinstance(parent, Branch):
                self._git.push(".", "{}:refs/heads/{}".format(commit_id, parent.name))
        # The commit will have no parent
        else:
            commit_id = self._git(
                "commit-tree",
                tree,
                "-m '{}'".format(msg),
            ).strip()

        return self.__obj_to_commit(commit_id)

    def get_branch_from_str(self, name: str) -> Branch | None:
        for b in self.branches():
            if name == b.name:
                return b
        return None

    def new_branch(self, name: str, cid: Reference | None = None) -> Branch:
        if not cid:
            cid = self.revparse(Branch(self, name="master")).cid

        self._git.push(".", "{}:refs/heads/{}".format(cid, name))
        return Branch(self, name=name)

    def set_branch(self, branch: Branch, commit: Reference) -> None:
        self._git.push("-f", ".", "{}:refs/heads/{}".format(commit.cid, branch.name))

    def list_files(self, rev: Reference | None = None, prefix: str = "") -> list[str]:
        if not rev:
            rev = ""
        return [self._git("ls-files", rev).strip().split("\n")]

    def list_commits(
        self,
        rev: Reference | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Commit]:
        rev = self._set_or_head(rev)
        if since:
            since = "--since={}".format(since)
        if until:
            until = "--until={}".format(until)

        return [self.__commit_info_getter("%H", rev, since, until)]

    def __commit_info_getter(self, pattern, *args):
        return self._git("--no-pager", "log", "--format={}".format(pattern), *args).strip()

    def diff_tree(self, prefix=None, src_rev=None, dst_rev=None):

        if not dst_rev:
            return None

        src_rev = self._set_or_head(src_rev)
        src_rev = self.revparse(src_rev)

        return self._git("diff-tree", src_rev, dst_rev).strip()

    def gc(self):
        self._git.gc("--aggressive")

    def get_parents(self, ref):
        ref = self._set_or_head(ref)
        ref = self.revparse(ref)

        parents = []
        for elt in self._git("cat-file", "-p", ref).strip().split("\n"):
            parents.append(self.__obj_to_commit(elt))
        return parents


def elect_handler(prefix: str | None = None) -> GitByGeneric:
    """Select the proper repository handler based on python support

    Python 3.10+-based PCVS installations come with pygit2, thanks to provided
    wheels. Older versions are relying on regular Git commands (as wheels are
    not provided for Python3.6 and older & building pygit2 requires specific
    libgit2 version to be installed, hardening the installation process)

    :param prefix: the git handle prefix.
    :return: The Git object representation with the correct handle.
    """
    if HAS_PYGIT2:
        git_handle = GitByAPI(prefix)
    else:
        git_handle = GitByCLI(prefix)

    return git_handle


def request_git_attr(k: str) -> str:
    """Get a git configuration.

    :param k: parameter to get
    :return: a git configuration
    """
    try:
        git_conf = {}
        # TODO: not only look for user config
        if HAS_PYGIT2:
            git_conf = pygit2.Config.get_global_config()
        else:
            git_conf[k] = sh.git.config("--get", k).strip()
        if k in git_conf:
            return git_conf[k]
    except IOError:
        # to user config
        pass
    return None


def generate_data_hash(data: str) -> str:
    """Hash data with git protocol.

    :param data: data to hash
    :return: hashed data
    """
    c = hashlib.md5()
    if not isinstance(data, bytes):
        data = str(data).encode()
    c.update(data)
    return c.hexdigest()


def get_current_username() -> str:
    """Get the git username.

    :return: git username
    """
    try:
        u = request_git_attr("user.name")
        if u is None:
            u = getpass.getuser()
        return u
    except Exception:
        pass

    return "anonymous"


def get_current_usermail() -> str:
    """Get the git user mail.

    :return: git user mail
    """
    m = None
    try:
        m = request_git_attr("user.email")
        if m is not None:
            return m
    except Exception:
        pass

    return "anonymous@notset"
