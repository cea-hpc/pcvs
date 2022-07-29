import fcntl
import os
import tarfile
import tempfile
import time
import json
from typing import Dict, List, Optional

from ruamel.yaml import YAML

from pcvs import NAME_BUILD_CONF_FN, NAME_BUILD_RESDIR, PATH_BANK
from pcvs.helpers import git
from pcvs.helpers.exceptions import BankException
from pcvs.helpers.system import MetaDict
from pcvs import dsl

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
        self._dflt_proj = None
        self._name = None
        self._config: Optional[MetaDict] = None
        
        # split name & default-proj from token
        array: List[str] = token.split('@', 1)
        if len(array) > 1:
            self._dflt_proj  = array[1]
        self._name = array[0]

        global BANKS
        self._path = path
        if self.exists():
            if self.name_exist():
                path = BANKS[self._name.lower()]
            else:
                for k, v in BANKS.items():
                    if v == path:
                        self._name = k
                        break
        
        super().__init__(path, self._dflt_proj )
    
    @property
    def default_project(self):
        return "unkwown" if not self._dflt_proj else self._dflt_proj

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
        return self._name

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
        return self._path in BANKS.values()
        
    def __str__(self) -> str:
        """Stringification of a bank.

        :return: a combination of name & path
        :rtype: str
        """
        return str({self._name: self._path})

    def show(self, stringify=False) -> None:
        """Print the bank on stdout.

        .. note::
            This function does not use :class:`log.IOManager`
        """
        string = ["Projects contained in bank '{}':".format(self._path)]
        # browse references
        for project, series in self.list_all().items():
            string.append("- {:<8}: {} distinct testsuite(s)".format(project, len(series)))
            for s in series:
                string.append("  * {}: {} run(s)".format(s.name, len(s)))

        if stringify:
            return "\n".join(string)
        else:
            print("\n".join(string))

    def __del__(self) -> None:
        """Close the bank."""
        self.disconnect()

    def save_to_global(self) -> None:
        """Store the current bank into ``PATH_BANK`` file."""
        global BANKS
        if self._name in BANKS:
            self._name = os.path.basename(self._path).lower()
        add_banklink(self._name, self._path)
        
    def load_config_from_str(self, s: str) -> None:
        """Load the configuration data associated with the archive to process.

        :param s: the configuration data
        :type s: str
        """
        self._config = MetaDict(YAML(typ='safe').load(s))
        
    def load_config_from_dict(self, s: dict) -> None:
        """TODO:
        """
        self._config = MetaDict(s)

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
        rawdata_dir = os.path.join(buildpath, NAME_BUILD_RESDIR)
        
        seriename = self.build_target_branch_name(tag)
        serie = self.get_serie(seriename)
        
        if not serie:
            serie = self.new_serie(seriename)
            
        run = dsl.Run(from_serie=serie)
        metadata = {'cnt': {}}
        
        for result_file in os.listdir(rawdata_dir):
            d = {}
            with open(os.path.join(rawdata_dir, result_file), 'r') as fh:
                data = MetaDict(json.load(fh))
                # TODO: validate
            for elt in data['tests']:
                name = elt['id']['fq_name']
                state = str(elt['result']['state'])
                metadata['cnt'].setdefault(state, 0)
                metadata['cnt'][state] += 1
                d[name] = elt
                
            run.update_flatdict(d)
        
        self.set_id(
            an=self._config.validation.author.name,
            am=self._config.validation.author.email,
            cn=git.get_current_username(),
            cm=git.get_current_usermail()
        )

        serie.commit(run, metadata=metadata, timestamp=int(self._config.validation.datetime.timestamp()))

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
            self.save_from_buildir(
                tag, os.path.join(tarpath, "save_for_export"))

    def build_target_branch_name(self, tag: str=None, hash: str=None) -> str:
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
        if hash is None:
            hash = self._config.validation.pf_hash
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
        """TODO:
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
