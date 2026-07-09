import getpass
import hashlib
import os
from datetime import datetime
from typing import Any
from typing import cast
from typing import Iterable

import pygit2
import sh
from typing_extensions import Self

from pcvs.helpers import utils
from pcvs.helpers.exceptions import GitException


class Reference:
    """Maps an object which can be "pointed" (as a Git semantic). It can usually
    be used to refer a commit, a simple hash or a branch."""

    def __init__(self, repo: pygit2.Repository) -> None:
        self._repo: pygit2.Repository = repo

    @property
    def repo(self) -> pygit2.Repository:
        """Getter to the repo this reference comes from."""
        return self._repo


class Branch(Reference):
    """Maps to a regular Git branch."""

    def __init__(self, handler: "Git", name: str = "master") -> None:
        super().__init__(handler._repo)  # type: ignore[arg-type]
        self._handler: Git = handler
        self._name: str = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def handler(self) -> "Git":
        return self._handler


class Commit(Reference):
    """Maps to a regular Git commit"""

    def __init__(
        self, repo: pygit2.Repository, obj: pygit2.Object, metadata: dict[str, Any] | None = None
    ) -> None:
        super().__init__(repo)
        if metadata is None:
            metadata = {}
        self.cid: pygit2.Commit = cast(pygit2.Commit, obj)
        self.meta: dict[str, Any] = metadata

    def get_info(self) -> dict[str, Any]:
        """
        Return commit metadata stored as a dict.

        It may contains extra infos compared to what a commit usually contains

        :return: The data attached to the commit object when initialized.
        """
        return self.meta


class Tree(Reference):
    """Maps to a git-lowlevel Tree object"""

    def __init__(
        self,
        repo: pygit2.Repository,
        tid: Any,
        prefix: str = "",
        children: list | None = None,
    ) -> None:
        super().__init__(repo)
        if children is None:
            children = []
        self.tid: Any = tid
        self.prefix: str = prefix
        self.children: list = children

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

    def __init__(
        self, repo: pygit2.Repository, tid: Any, prefix: str = "", data: bytes = b""
    ) -> None:
        super().__init__(repo, tid, prefix, children=[])
        self.data: bytes = data

    def __str__(self) -> str:
        """
        Stringify data contained in blob.

        :returns: the decoded data
        """
        return self.data.decode()


class Git:
    """
    Create a Git endpoint able to discuss efficiently with repositories.

    This class relies on the pygit2 Python module (requires libgit2).
    """

    # ------------------------------------------------------------------ #
    #  Construction / Initialization
    # ------------------------------------------------------------------ #

    def __init__(self, prefix: str | None = None, head: str = "unknown/00000000") -> None:
        self._path: str = ""
        self._lockname: str = ""
        self._lockfd: int | None = None
        self._authname: str = ""
        self._authmail: str = ""
        self._commmail: str = ""
        self._commname: str = ""
        self._repo: pygit2.Repository | None = None
        self._head: Branch = Branch(self, head)

        if prefix:
            self.set_path(prefix)

        self.set_identity(None, None, None, None)

    def set_path(self, prefix: str) -> None:
        """
        Associate a new directory to this bank.

        :param prefix: the prefix locating the Git repo
        """
        self._path = prefix
        self._lockname = os.path.join(prefix, ".pcvs")

    def set_identity(
        self,
        authname: str | None,
        authmail: str | None,
        commname: str | None,
        commmail: str | None,
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

    # ------------------------------------------------------------------ #
    #  HEAD management
    # ------------------------------------------------------------------ #

    def get_head(self) -> Branch:
        """Get the current repo's HEAD (used when no default)

        :returns: a ref to the HEAD as a branch
        """
        return self._head

    def set_head(self, branch_name: str) -> None:
        """Move the repo HEAD (used when no default ref is provided)"""
        self._head = Branch(self, branch_name)

    # ------------------------------------------------------------------ #
    #  Open / Close
    # ------------------------------------------------------------------ #

    def open(self, bare: bool = True) -> None:
        """
        Open the repo, with appropriate method.

        :param bare: true by default, manage or bare repo.
        """
        assert self._path
        assert not os.path.isfile(self._path)
        if not os.path.isdir(self._path) or len(os.listdir(self._path)) == 0:
            if not self._is_locked():
                self._repo = pygit2.init_repository(
                    self._path,
                    flags=(
                        pygit2.enums.RepositoryInitFlag.MKPATH
                        | pygit2.enums.RepositoryInitFlag.NO_REINIT
                    ),
                    mode=pygit2.enums.RepositoryInitMode.SHARED_GROUP,
                    bare=bare,
                )
                self._lock()
        else:
            rep = pygit2.discover_repository(self._path)
            if rep:
                self._repo = pygit2.Repository(rep)
                self._lock()

    def is_open(self) -> bool:
        """Is the directory currently open ?"""
        return self._is_locked()

    def close(self) -> None:
        """Unlock the repository."""
        self._unlock()

    # ------------------------------------------------------------------ #
    #  Locking
    # ------------------------------------------------------------------ #

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

    def _unlock(self) -> None:
        """
        Unlock the current repository.
        """
        utils.unlock_file(self._lockname)

    def _is_locked(self) -> bool:
        """Locked repo checker

        :return: true if the file is locked, false otherwise
        """
        return utils.is_locked(self._lockname)

    # ------------------------------------------------------------------ #
    #  Branch operations
    # ------------------------------------------------------------------ #

    def branches(self) -> list[Branch]:
        """
        Returns the list of available local branch names from this repo.
        """
        assert self._repo
        return [Branch(self, e) for e in self._repo.branches.local]

    def new_branch(self, name: str, cid: Reference | None = None) -> Branch:
        """
        Create a new branch.
        """
        assert name is not None
        assert self._repo is not None
        if cid is None:
            real_cid = self.revparse(Branch(self, name="master")).cid
        else:
            real_cid = self.revparse(cid).cid

        assert name not in self._repo.branches.local
        self._repo.branches.local.create(name, real_cid)
        return Branch(self, name=name)

    def get_branch_from_str(self, name: str) -> Branch | None:
        """
        Return the branch with name 'name'.
        """
        for b in self.branches():
            if name == b.name:
                return b
        return None

    def set_branch(self, branch: Branch, commit: Reference) -> None:
        """
        Set branch.
        """
        assert isinstance(commit, Reference)
        assert isinstance(branch, Branch)
        assert self._repo is not None

        pygit_obj = self.revparse(commit).cid.id
        ref = "refs/heads/{}".format(branch.name)
        if ref in self._repo.references:
            self._repo.references.delete(branch.name)
        self._repo.references.create("refs/heads/{}".format(branch.name), pygit_obj)

    # ------------------------------------------------------------------ #
    #  Revision parsing / Helpers
    # ------------------------------------------------------------------ #

    def revparse(self, rev: Reference) -> Commit:
        """
        Convert a revision (tag, branch, commit) to a regular reference.

        :param rev: Reference
        :return: the resolved commit
        """
        assert self._repo is not None
        assert isinstance(rev, Reference)

        if isinstance(rev, Commit):
            return rev

        assert isinstance(rev, Branch)
        o: pygit2.Object = self._repo.revparse_single(rev.name)
        return self.__obj_to_commit(o)

    def _set_or_head(self, rev: Reference | None) -> Reference:
        """
        Return a valid revision to be used

        If rev is not set, return the default HEAD repo.

        :param rev: the revision to use or replace if not set
        :return: The reference or head.
        """
        if rev is not None:
            return rev
        return self._head

    def __obj_to_commit(self, obj: pygit2.Object) -> Commit:
        assert self._repo is not None
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

    # ------------------------------------------------------------------ #
    #  Tree operations
    # ------------------------------------------------------------------ #

    def get_tree(self, tree: Reference | None = None, prefix: str = "") -> Blob | Tree | None:
        """
        Retrieve data associated with a given prefix. A tree can used
        to set which ref should be used.

        :param tree: the ref from where get the data
        :param prefix: the unique prefix associated with data
        :return: the Blob or Tree at the given prefix, or None
        """
        rev = self._set_or_head(tree)

        gtree: pygit2.Commit | None = None
        if isinstance(rev, Branch):
            assert self._repo is not None
            gtree = self._repo.revparse_single(rev.name).tree
        elif isinstance(rev, Commit):
            gtree = rev.cid.tree

        if prefix:
            tid = self._get_tree(prefix.split("/"), gtree)
        else:
            tid = gtree

        if tid is None:
            return None
        assert self._repo is not None
        if isinstance(tid, pygit2.Blob):
            return Blob(self._repo, tid, prefix, tid.data)
        return Tree(self._repo, tid, prefix)

    def _get_tree(self, chain: list[str], tree: pygit2.Commit | None = None) -> Any | None:
        if len(chain) <= 0:
            return tree
        if tree is None:
            return None
        subtree = None
        for file in tree:
            if chain[0] == file.name:
                subtree = file
                break
        else:
            return None  # file you are looking for does not exist in this git
        return self._get_tree(chain[1:], subtree)

    def insert_tree(self, prefix: str, data: Any, root: Tree | None = None) -> Tree:
        """
        Create a new tree mapping a prefix filled with 'data'.

        :param prefix: the prefix under Git tree.
        :param data: the data to store.
        :param root: the root tree  to insert the data in.
        :return: the root Tree containing the inserted data
        """
        assert self._repo is not None
        if not root:
            root = Tree.as_root(self._repo, self._repo.TreeBuilder())

        pygit_obj: pygit2.TreeBuilder = root.hdl  # type: ignore[attr-defined]
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
        assert self._repo is not None

        # the basename is reached -> generate the blob and return the parend oid
        if len(path) == 1:
            data_hash = pygit2.hash(str(data))
            if data_hash in self._repo:
                data_obj = self._repo[data_hash].id
            else:
                data_obj = self._repo.create_blob(str(data))
            treebuild.insert(path[0], data_obj, pygit2.enums.FileMode.BLOB)
            return treebuild.write()

        # otherwise, determine where the current subdir is going
        subtree_name = path[0]
        tree = self._repo.get(treebuild.write())
        assert tree is not None
        tree_obj = cast(pygit2.Tree, tree)

        try:
            # check if the subdir already exist in this bank subtree
            entry = tree_obj[subtree_name]
            assert entry.filemode == pygit2.enums.FileMode.TREE
            subtree = self._repo.get(str(entry.id))
            # YES it is found -> reuse this subtree
            assert subtree is not None
            sub_treebuild = self._repo.TreeBuilder(cast(pygit2.Tree, subtree))
        except KeyError:
            # NOPE: first time adding a resource to this subtree
            # create a new one
            sub_treebuild = self._repo.TreeBuilder()

        # recursive call, as we didn't reach the subtree bottom
        subtree_oid = self.__insert_path(sub_treebuild, path[1:], data)
        # Pygit2 insert, to build the actual intermediate node
        treebuild.insert(subtree_name, subtree_oid, pygit2.enums.FileMode.TREE)
        return treebuild.write()

    # ------------------------------------------------------------------ #
    #  Diff / Traversal
    # ------------------------------------------------------------------ #

    def diff_tree(
        self,
        prefix: str | None = None,
        src_rev: Reference | None = None,
        dst_rev: Reference | None = None,
    ) -> list[str]:
        """Compare two revisions and return the content of changed files.

        For each file that was added or modified between src_rev and dst_rev,
        returns the content of that file as a string from the dst_rev tree.

        :param prefix: optional path prefix to filter results
        :param src_rev: the source revision
        :param dst_rev: the destination revision
        :return: list of file contents as strings
        """
        src_rev = self._set_or_head(src_rev)
        src_rev = self.revparse(src_rev)

        dst_rev = self._set_or_head(dst_rev)
        dst_rev = self.revparse(dst_rev)

        src_tree = src_rev.cid.tree
        dst_tree = dst_rev.cid.tree

        diff = src_tree.diff_to_tree(dst_tree)

        results: list[str] = []
        for delta in diff.deltas:
            path = delta.new_file.path
            if not path:
                continue
            if prefix and not path.startswith(prefix):
                continue
            data = self.get_tree(tree=dst_rev, prefix=path)
            if isinstance(data, Blob):
                results.append(str(data))

        return results

    def iterate_over(self, ref: Reference) -> Iterable[Commit]:
        """starting from the ref, iterate references backwards (from newest to
        oldest).

        :param ref: the starting point
        :yields: the commit objects from oldest to newest
        """
        assert isinstance(ref, Reference)
        assert self._repo is not None
        rev = self._set_or_head(ref)
        rev = self.revparse(rev)
        assert isinstance(rev, Commit)
        pygit_obj = rev.cid

        for o in self._repo.walk(pygit_obj.id, pygit2.enums.SortMode.REVERSE):
            yield self.__obj_to_commit(o)

    def list_files(self, rev: Reference | None = None, prefix: str = "") -> list[str]:
        """For a given revision, list files (not only changed ones).

        :param rev: the reference
        :param prefix: the prefix
        :return: the list of file paths
        """
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
        :return: the list of commits in the given date range
        """
        res = []
        assert not rev or isinstance(rev, Reference)

        if since is None:
            since = datetime.now()

        if until is None:
            until = datetime.fromtimestamp(0)

        for c in self.iterate_over(self._set_or_head(rev)):
            pygit_obj = c.cid
            if (
                pygit_obj.commit_time <= since.timestamp()
                and pygit_obj.commit_time >= until.timestamp()
            ):
                res.append(self.__obj_to_commit(pygit_obj))
        return res

    # ------------------------------------------------------------------ #
    #  Commit operations
    # ------------------------------------------------------------------ #

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
        :return: the created commit
        :raises BadEntryError: if the parent reference is unknown
        """
        assert self._repo is not None
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
                parents = [self.revparse(parent).cid.id]
            elif isinstance(parent, Commit):
                update_ref = None
                parents = [parent.cid.id]
            else:
                raise GitException.BadEntryError(
                    reason="Parent is unknown", dbg_info={"ref": str(parent)}
                )

        coid = self._repo.create_commit(
            update_ref, author, committer, msg, tree.hdl.write(), parents  # type: ignore[attr-defined]
        )
        ci = self._repo.get(coid)
        assert ci is not None
        return self.__obj_to_commit(cast(pygit2.Commit, ci))

    # ------------------------------------------------------------------ #
    #  Miscellaneous
    # ------------------------------------------------------------------ #

    def gc(self) -> None:
        """Run the garbage collector"""
        assert self._path
        hdl = sh.git.bake(_cwd=self._path)
        hdl.gc()

    def get_parents(self, ref: Reference) -> list[Commit]:
        """Retrieve parents for a given ref.

        :param ref: the revision
        :return: the list of parent commits
        """
        assert isinstance(ref, Reference)

        ref = self._set_or_head(ref)
        ref = self.revparse(ref)

        return [self.__obj_to_commit(p) for p in ref.meta["parents"]]


# Backward compatibility aliases
GitByGeneric = Git
GitByAPI = Git


def elect_handler(prefix: str | None = None) -> Git:
    """Select the proper repository handler.

    Returns a Git instance backed by pygit2.

    :param prefix: the git handle prefix.
    :return: The Git object representation.
    """
    return Git(prefix)


def request_git_attr(k: str) -> str | None:
    """Get a git configuration.

    :param k: parameter to get
    :return: a git configuration
    """
    try:
        git_conf = pygit2.Config.get_global_config()
        if k in git_conf:
            return str(git_conf[k])
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
    c.update(data.encode())
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
