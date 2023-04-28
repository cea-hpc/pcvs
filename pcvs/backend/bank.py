import fcntl
import json
import os
import tarfile
import tempfile
import time
from typing import Dict, List, Optional

from ruamel.yaml import YAML

from pcvs import NAME_BUILD_CONF_FN, NAME_BUILD_RESDIR, PATH_BANK, dsl
from pcvs.helpers import utils
from pcvs.helpers import git
from pcvs.orchestration.publishers import BuildDirectoryManager
from pcvs.helpers.exceptions import BankException, CommonException
from pcvs.helpers.system import MetaDict

#: :var BANKS: list of available banks when PCVS starts up
#: :type BANKS: dict, keys are bank names, values are file path
BANKS: Dict[str, str] = dict()


class Bank(dsl.Bank):
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
    :param proj_name: extracted default-proj from initial token
    :type proj_name: str
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
        self._dflt_proj: Optional[str] = None
        self._name: Optional[str] = None
        self._path: str = path

        global BANKS

        # split name & default-proj from token
        array: List[str] = token.split('@', 1)
        if len(array) > 1:
            self._dflt_proj = array[1]
        self._name = array[0]

        if self.exists():
            if self.name_exist():
                path = BANKS[self._name.lower()]
            else:
                for k, v in BANKS.items():
                    if v == path:
                        self._name = k
                        break

        super().__init__(path, self._dflt_proj)

    @property
    def default_project(self) -> str:
        """
        Get project set as default when none are provided.

        :return: the project name (as a Ref branch)
        :rtype: str
        """
        return "unknown" if not self._dflt_proj else self._dflt_proj

    @property
    def prefix(self) -> Optional[str]:
        """Get path to bank directory.

        :return: absolute path to directory
        :rtype: str
        """
        return self._path

    @property
    def name(self) -> str:
        """Get bank name.

        :return: the exact label (without default-project suffix)
        :rtype: str
        """
        return self._name if self._name else ""

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
        return self._name.lower() in BANKS.keys() if self._name else False

    def path_exist(self) -> bool:
        """Check if the bank path is registered into ``PATH_BANK`` file.

        :return: True if the path is known.
        :rtype: bool
        """
        return self._path in BANKS.values()

    def __str__(self) -> str:
        """Stringification of a bank.

        :return: a combination of name & path
        :rtype: str
        """
        return str({self._name: self._path})

    def show(self, stringify: bool = False) -> Optional[str]:
        """Print the bank on stdout.

        .. note::
            This function does not use :class:`log.IOManager`
        """
        string = ["Projects contained in bank '{}':".format(self._path)]
        # browse references
        for project, series in self.list_all().items():
            string.append(
                "- {:<8}: {} distinct testsuite(s)".format(project, len(series)))
            for s in series:
                string.append("  * {}: {} run(s)".format(s.name, len(s)))

        if stringify:
            return "\n".join(string)
        else:
            print("\n".join(string))

    def __del__(self) -> None:
        """
        Close / disconnet a bank (releasing lock)
        """
        self.disconnect()

    def save_to_global(self) -> None:
        """Store the current bank into ``PATH_BANK`` file."""
        global BANKS
        if self._name in BANKS:
            self._name = os.path.basename(self._path).lower()
        add_banklink(self._name, self._path)

    def save_from_buildir(self, tag: str, buildpath: str, msg: str=None) -> None:
        """Extract results from the given build directory & store into the bank.

        :param tag: overridable default project (if different)
        :type tag: str
        :param buildpath: the directory where PCVS stored results
        :type buildpath: str
        """
        hdl = BuildDirectoryManager(buildpath)
        hdl.load_config()
        hdl.init_results()
        
        seriename = self.build_target_branch_name(tag, hdl.config.validation.pf_hash)
        serie = self.get_serie(seriename)
        if serie is None:
            serie = self.new_serie(seriename)

        run = dsl.Run(from_serie=serie)
        metadata = {'cnt': {}}

        for job in hdl.results.browse_tests():
            metadata['cnt'].setdefault(str(job.state), 0)
            metadata['cnt'][str(job.state)] += 1
            run.update(job.name, job.to_json())
            
        self.set_id(
            an=hdl.config.validation.author.name,
            am=hdl.config.validation.author.email,
            cn=git.get_current_username(),
            cm=git.get_current_usermail()
        )
        
        run.update(".pcvs-cache/conf.json", hdl.config.dump_for_export())

        serie.commit(run, metadata=metadata, msg=msg, timestamp=int(
            hdl.config.validation.datetime.timestamp()))

    def save_from_archive(self, tag: str, archivepath: str, msg: str=None) -> None:
        """Extract results from the archive, if used to export results.

        This is basically the same as :func:`BanK.save_from_buildir` except
        the archive is extracted first.

        :param tag: overridable default project (if different)
        :type tag: str
        :param archivepath: archive path
        :type archivepath: str
        """
        assert (os.path.isfile(archivepath))

        with tempfile.TemporaryDirectory() as tarpath:
            tarfile.open(os.path.join(archivepath)).extractall(tarpath)
            d = [x for x in os.listdir(tarpath) if x.startswith("pcvsrun_")]
            assert(len(d) == 1)
            self.save_from_buildir(tag, os.path.join(tarpath, d[0]), msg=msg)
            
    def save_new_run_from_instance(self, target_project: str, hdl: BuildDirectoryManager, msg: str=None) -> None:
        """
        Create a new node into the bank for the given project, based on the open
        result handler.

        :param target_project: valid project (=branch)
        :type target_project: str
        :param hdl: the result build directory handler
        :type hdl: class:`BuildDirectoryManager`
        """
        seriename = self.build_target_branch_name(target_project, hdl.config.validation.pf_hash)
        serie = self.get_serie(seriename)
        metadata = {'cnt': {}}
        
        if serie is None:
            serie = self.new_serie(seriename)
        
        #TODO: populate the run with build-dir content
        #TODO: add metadata to hidden root directory
        # Init a new fun
        run = dsl.Run(from_serie=serie)

        # now use the handle to populate the bank
        # We chose to make the layout slightly different between
        # runs & banks as the `git-diff` does not permit to store
        # other than a JSON file per test output (yet) :(
        # Still, an hidden root directory will store aliases to easily
        # maps tests to their on-disk counterparts.
        d = dict()
        for job in hdl.results.browse_tests():
            d[job.name] = job.to_json()
            metadata['cnt'].setdefault(str(job.state), 0)
            metadata['cnt'][str(job.state)] += 1
    
        run.update_flatdict(d)
        
        self.set_id(
            an=hdl.config.validation.author.name,
            am=hdl.config.validation.author.email,
            cn=git.get_current_username(),
            cm=git.get_current_usermail()
        )
        
        run.update(".pcvs-cache/conf.json", hdl.config)
        
        serie.commit(run, metadata=metadata, msg=msg, timestamp=int(
            hdl.config.validation.datetime.timestamp()))

    def save_new_run(self, target_project: str, path: str) -> None:
        if not utils.check_is_build_or_archive(path):
            raise CommonException.NotPCVSRelated(
                reason="Invalid path, not PCVS-related",
                dbg_info={"path": path}
            )

        if utils.check_is_archive(path):
            # convert to prefix
            # update path according to it
            hdl = BuildDirectoryManager.load_from_archive(path)
        else:
            hdl = BuildDirectoryManager(build_dir=path)
            hdl.load_config()

        self.save_new_run_from_instance(target_project, hdl)
        
    def build_target_branch_name(self, tag: str = None, hash: str = None) -> str:
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
            tag = self.default_project
        return "{}/{}".format(tag, hash)

    def __repr__(self) -> dict:
        """Bank representation.

        :return: a dict-based representation
        :rtype: dict
        """
        return {
            'rootpath': self._path,
            'name': self._name
        }

    def get_count(self):
        """
        Get the number of projects managed by this bank handle.

        :return: number of projects
        :rtype: int
        """
        return len(self.list_projects())


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
