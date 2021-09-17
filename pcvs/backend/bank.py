import fcntl
import os
import tarfile
import tempfile
import time
from typing import Dict, List, Optional

import pygit2
from ruamel.yaml import YAML

from pcvs import NAME_BUILD_CONF_FN, NAME_BUILD_RESDIR, PATH_BANK
from pcvs.helpers import git
from pcvs.helpers.exceptions import BankException
from pcvs.helpers.system import MetaDict

#: :var BANKS: list of available banks when PCVS starts up
#: :type BANKS: dict, keys are bank names, values are file path
BANKS: Dict[str, str] = dict()


class Bank:
    """Representation of a PCVS result datastore.

    Stored as a Git repo, a bank hold multiple results to be scanned and used to
    analyse benchmarks result over time. A single bank can manipulate namespaces
    (referred as 'projects'). The namespace is provided by suffixing ``@proj``
    to the original name.

    :param root: the root bank directory
    :type root: str
    :param repo: the Pygit2 handle
    :type repo:  :class:`Pygit2.Repository`
    :param config: when set, configuration file of the just-submitted archive
    :type config: :class:`MetaDict`
    :param rootree: When set, root handler to the next commit to insert
    :type rootree: :class:`Pygit2.Object`
    :param locked: Serialize Bank manipulation among multiple processes
    :type locked: bool
    :param preferred_proj: extracted default-proj from initial token
    :type preferred_proj: str
    """

    def __init__(self, path: Optional[str] = None, token: str = "") -> None:
        """Build a Bank.

        The path may be omitted if the bank is already known (=stored in
        ``PATH_BANK`` file). If not, the path is mandatory in order to be saved.

        .. warning::
            A bank name should be resolved either by its presence in
            ``PATH_BANK`` file **or** with a valid provided path. Otherwise, an
            error may be raised.

        The token is under the form ``A@B`` where ``A`` depicts its name and
        ``B`` represents the "default" project" where data will be manipulated.

        :param path: location of the bank repo (on disk), defaults to None
        :type path: str, optional
        :param token: name & default project to manipulate, defaults to ""
        :type token: str
        """
        self._root: Optional[str] = path
        self._repo: Optional[pygit2.Repository] = None
        self._config: Optional[MetaDict] = None
        self._rootree: Optional[pygit2.TreeBuilder] = None
        self._locked: bool = False
        self._preferred_proj: Optional[str] = None

        # split name & default-proj from token
        array: List[str] = token.split('@', 1)
        if len(array) > 1:
            self._preferred_proj = array[1]
        self._name = array[0]

        global BANKS
        if self.exists():
            if self.name_exist():
                self._root = BANKS[self._name.lower()]
            else:
                for k, v in BANKS.items():
                    if v == self._root:
                        self._name = k
                        break

    @property
    def prefix(self) -> Optional[str]:
        """Get path to bank directory.

        :return: absolute path to directory
        :rtype: str
        """
        return self._root

    @property
    def name(self) -> str:
        """Get bank name.

        :return: the exact label (without default-project suffix)
        :rtype: str
        """
        return self._name

    @property
    def preferred_proj(self) -> Optional[str]:
        """Get default-project tag.

        :return: the exact project (without bank label prefix)
        :rtype: str
        """
        return self._preferred_proj

    def exists(self) -> bool:
        """Check if the bank is stored in ``PATH_BANK`` file.

        Verification is made either on name **or** path.

        :return: True if both the bank exist and globally registered
        :rtype: bool
        """
        return self.name_exist() or self.path_exist()

    def name_exist(self) -> bool:
        """Check if the bank name is registered into ``PATH_BANK`` file.

        :return: True if the name (lowered) is in the keys()
        :rtype: bool
        """
        return self._name.lower() in BANKS.keys()

    def path_exist(self) -> bool:
        """Check if the bank path is registered into ``PATH_BANK`` file.

        :return: True if the path is known.
        :rtype: bool
        """
        return self._root in BANKS.values()

    def list_projects(self) -> List[str]:
        """Given the bank, list projects with at least one run.

        In a bank, each branch is a project, just list available branches.
        `master` branch is not a valid project.

        :return: A list of available projects
        :rtype: list of str
        """
        INVALID_REFS = ["refs/heads/master"]
        # a ref is under the form: 'refs/<bla>/NAME/<hash>
        return [elt.split('/')[2] for elt in self._repo.references if elt not in INVALID_REFS]

    def __str__(self) -> str:
        """Stringification of a bank.

        :return: a combination of name & path
        :rtype: str
        """
        return str({self._name: self._root})

    def show(self) -> None:
        """Print the bank on stdout.

        .. note::
            This function does not use :class:`log.IOManager`
        """
        projects = dict()
        s = ["Projects contained in bank '{}':".format(self._root)]
        # browse references
        for b in self._repo.references:
            if b == 'refs/heads/master':
                continue
            name = b.split("/")[2]
            projects.setdefault(name, list())
            projects[name].append(b.split("/")[3])

        # for each project, list 'run variants', each having a different hash
        for pk, pv in projects.items():
            s.append("- {:<8}: {} distinct testsuite(s)".format(pk, len(pv)))
            for v in pv:
                nb_parents = 1
                cur, _ = self._repo.resolve_refish("{}/{}".format(pk, v))
                while len(cur.parents) > 0:
                    nb_parents += 1
                    cur = cur.parents[0]

                s.append("  * {}: {} run(s)".format(v, nb_parents))

        print("\n".join(s))

    def __del__(self) -> None:
        """Close the bank."""
        self.disconnect_repository()

    def disconnect_repository(self) -> None:
        """Free the bank repo, to be reused by other instance."""
        if self._locked:
            self._locked = False
            fcntl.flock(self._lockfile, fcntl.LOCK_UN)

    def connect_repository(self) -> None:
        """Connect to the bank repo, making it exclusive to the current process.

        Two scenarios:
            * the path is empty -> create a new bank
            * the path is not empty -> detect a bank repo.

        In any cases, lock the directory to prevent multiple accesses.

        :raises AlreadyExistError: A bank is already built
        :raises NotFoundError: the given path does not contain a
            Git directory.
        """
        if self._repo is None:
            if not os.path.isfile(os.path.join(self._root, 'HEAD')):
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
                    raise BankException.AlreadyExistError()
                # can't be moved before as self._root may not exist yet
                self._lockfile = open(os.path.join(
                    self._root, ".pcvs.lock"), 'w+')
            else:
                rep = pygit2.discover_repository(self._root)
                if rep:
                    # need to lock, to ensure safety
                    self._root = rep.rstrip("/")
                    self._lockfile = open(os.path.join(
                        self._root, ".pcvs.lock"), 'w+')
                    locked = False
                    while not locked:
                        try:
                            fcntl.flock(self._lockfile,
                                        fcntl.LOCK_EX | fcntl.LOCK_NB)
                            locked = True
                        except BlockingIOError:
                            time.sleep(1)

                    self._repo = pygit2.Repository(rep)
                else:
                    raise BankException.NotFoundError()
            self._locked = True

    def save_to_global(self) -> None:
        """Store the current bank into ``PATH_BANK`` file."""
        global BANKS
        if self._name in BANKS:
            self._name = os.path.basename(self._root).lower()
        add_banklink(self._name, self._root)

    def create_test_blob(self, data: str) -> pygit2.Object:
        """Create a small hashed object, to be stored into a bank.

        :param data: any type of data to be stored. In PCVS context, it is
            mainly json-formatted strings.
        :param data: str

        :return: the pygit2-hashed representation id
        :rtype: :class:`pygit2.Object`
        """
        assert(isinstance(self._repo, pygit2.Repository))

        data_hash = pygit2.hash(str(data))
        if data_hash in self._repo:
            return self._repo[data_hash].oid
        else:
            return self._repo.create_blob(str(data))

    def insert(self, treebuild: pygit2.TreeBuilder, path: List[str], obj: any) -> pygit2.Object:
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
            blob_obj = self.create_test_blob(obj)
            treebuild.insert(path[0], blob_obj, pygit2.GIT_FILEMODE_BLOB)
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
        subtree_oid = self.insert(sub_treebuild, path[1:], obj)
        # Pygit2 insert, to build the actual intemediate node
        treebuild.insert(subtree_name, subtree_oid, pygit2.GIT_FILEMODE_TREE)
        return treebuild.write()

    def save_test_from_json(self, jtest: str) -> pygit2.Object:
        """Store data to a bank directly from JSON representation.

        This is mainly used when a bank is directly connected to a run instance,
        not intermediate file is required.

        :param jtest: the JSON-formatted test result
        :type jtest: str
        :return: the blob object id
        :rtype: :class:`Pygit2.Oid`
        """
        assert('validation' in self._config)
        test_track = jtest['id']['fq_name'].split("/")
        oid = self.insert(self._rootree, test_track, jtest.to_dict())
        return oid

    def load_config_from_str(self, s: str) -> None:
        """Load the configuration data associated with the archive to process.

        :param s: the configuration data
        :type s: str
        """
        self._config = MetaDict(YAML(typ='safe').load(s))

    def load_config_from_file(self, path: str) -> None:
        """Load the configuration file associated with the archive to process.

        :param path: the configuration file path
        :type path: str
        """
        with open(os.path.join(path, NAME_BUILD_CONF_FN), 'r') as fh:
            self._config = MetaDict(YAML(typ='safe').load(fh))

    def save_from_buildir(self, tag: str, buildpath: str) -> None:
        """Extract results from the given build directory & store into the bank.

        :param tag: overridable default project (if different)
        :type tag: str
        :param buildpath: the directory where PCVS stored results
        :type buildpath: str
        """
        self.load_config_from_file(buildpath)
        self._rootree = self._repo.TreeBuilder()

        rawdata_dir = os.path.join(buildpath, NAME_BUILD_RESDIR)
        for result_file in os.listdir(rawdata_dir):
            with open(os.path.join(rawdata_dir, result_file), 'r') as fh:
                data = MetaDict(YAML(typ='safe').load(fh))
                # TODO: validate

            for elt in data['tests']:
                self.save_test_from_json(elt)
        self._rootree.write()
        self.finalize_snapshot(tag)

    def save_from_archive(self, tag: str, archivepath: str) -> None:
        """Extract results from the archive, if used to export results.

        This is basically the same as :func:`BanK.save_from_buildir` except
        the archive is extracted first.

        :param tag: overridable default project (if different)
        :type tag: str
        :param archivepath: archive path
        :type archivepath: str
        """
        assert(os.path.isfile(archivepath))

        with tempfile.TemporaryDirectory() as tarpath:
            tarfile.open(os.path.join(archivepath)).extractall(tarpath)
            os
            self.save_from_buildir(
                tag, os.path.join(tarpath, "save_for_export"))

    def finalize_snapshot(self, tag: str) -> None:
        """Finalize result submission into the bank.

        After walking through build directory, finalize the Git tree to insert a
        commit on top of the created tree.

        :param tag: overridable default project (if different)
        :type tag: str
        """
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
            name=git.get_current_username(),
            email=git.get_current_usermail())
        commit_msg = "Commit message is not used (yet)"

        refname = self.__build_target_branch_name(tag)

        # check if the current reference already exist.
        # if so, retrieve the parent commit to be linked
        if refname in self._repo.references:
            parent_commit, ref = self._repo.resolve_refish(refname)
            parent_coid = [parent_commit.oid]
        else:
            # otherwise the commit to be created will be the first
            # and won't have any parent
            parent_coid = []
            ref = MetaDict({"name": None})

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

    def __build_target_branch_name(self, tag: str) -> str:
        """Compute the target branch to store data.

        This is used to build the exact Git branch name based on:
            * default-proj
            * unique profile hash, used to run the validation

        :param tag: overridable default-proj (if different)
        :type tag: str
        :return: fully-qualified target branch name
        :rtype: str
        """
        # a reference (lightweight branch) is tracking a whole test-suite
        # history, there are managed directly
        # TODO: compute the proper name for the current test-suite
        if tag is None:
            tag = self._preferred_proj

            if tag is None:
                tag = "unknown"
        return "refs/heads/{}/{}".format(tag, self._config.validation.pf_hash)

    def extract_data(self, key, start, end, format):
        """Extract information from the bank given specifications.

        .. note::
            This function is still WIP.

        :param key: the requested key
        :type key: str
        :param start: start time
        :type start: date
        :param end: end time
        :type end: date
        :param format: Not relevant yet
        :type format: Not relevant yet
        :raises ProjectNameError: Targeted project does not exist
        """
        refname = self.__build_target_branch_name(None)

        if refname not in self._repo.references:
            raise BankException.ProjectNameError()

        head, _ = self._repo.resolve_refish(refname)
        for commit in self._repo.walk(head, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE):
            print(commit.message, commit.author.date)

    def __repr__(self) -> dict:
        """Bank representation.

        :return: a dict-based representation
        :rtype: dict
        """
        return {
            'rootpath': self._root,
            'name': self._name,
            'locked': self._locked
        }


def init() -> None:
    """Bank interface detection.

    Called when program initializes. Detects defined banks in ``PATH_BANK``
    """
    global BANKS
    try:
        with open(PATH_BANK, 'r') as f:
            BANKS = YAML(typ='safe').load(f)
    except FileNotFoundError:
        # nothing to do, file may not exist
        pass
    if BANKS is None:
        BANKS = dict()


def list_banks() -> dict:
    """Accessor to bank dict (outside of this module).

    :return: dict of available banks.
    :rtype: dict
    """
    return BANKS


def add_banklink(name: str, path: str) -> None:
    """Store a new bank to the global system.

    :param name: bank label
    :type name: str
    :param path: path to bank directory
    :type path: str
    """
    global BANKS
    BANKS[name] = path
    flush_to_disk()


def rm_banklink(name: str) -> None:
    """Remove a bank from the global management system.

    :param name: bank name
    :type name: str
    """
    global BANKS
    if name in BANKS:
        BANKS.pop(name)
        flush_to_disk()


def flush_to_disk() -> None:
    """Update the ``PATH_BANK`` file with in-memory object.

    :raises IOError: Unable to properly manipulate the tree layout
    """
    global BANKS, PATH_BANK
    try:
        prefix_file = os.path.dirname(PATH_BANK)
        if not os.path.isdir(prefix_file):
            os.makedirs(prefix_file, exist_ok=True)
        with open(PATH_BANK, 'w+') as f:
            YAML(typ='safe').dump(BANKS, f)
    except IOError as e:
        raise BankException.IOError(e)
