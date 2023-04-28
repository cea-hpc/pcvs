import bz2
import datetime
import json
import os
import shutil
import tarfile
import tempfile
from typing import Dict, List, Optional, Iterable

from ruamel.yaml import YAML

import pcvs
from pcvs import io
from pcvs.helpers import utils
from pcvs.helpers.exceptions import PublisherException, CommonException
from pcvs.helpers.system import MetaConfig, ValidationScheme
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


class ResultFile:
    """
    A instance manages a pair of file dedicated to load/store PCVS job results
    on disk.
    
    A job result is stored in two different files whens given to a single
    ResultFile:
    * <prefix>.json, containing metadata (rc, command...)
    * <prefix>.bz2 BZ2-compressed job data.
    
    a MAGIC_TOKEN is used to detect file/data corruption.
    """
    
    MAGIC_TOKEN = "PCVS-START-RAW-OUTPUT"

    def __init__(self, filepath, filename):
        """
        Initialize a new pair of output files.

        :param filepath: path where files will be located.
        :type filepath: str
        :param filename: prefix filename
        :type filename: str
        """
        self._fileprefix = filename
        self._path = filepath
        self._cnt = 0
        self._sz = 0
        self._data = {}

        prefix = os.path.join(filepath, filename)

        # R/W access & seek to the start of the file
        self._metadata_file = "{}.json".format(prefix)
        self._rawdata_file = "{}.bz2".format(prefix)

        try:
            if os.path.isfile(self._metadata_file):
                self.load()
        except:
            pass

        # no way to have a bz2 be opened R/W at once ? seems not :(
        self._rawout = bz2.open(self._rawdata_file, "a")
        self._rawout_reader = bz2.open(self._rawdata_file, "r")

    def close(self):
        """
        Close the current instance (flush to disk)
        """
        self.flush()
        if self._rawout:
            self._rawout.close()
            self._rawout = None

    def flush(self):
        """
        Sync cache with disk
        """
        with open(self._metadata_file, "w") as fh:
            json.dump(self._data, fh)

        if self._rawout:
            self._rawout.flush()

    def save(self, id, data, output):
        """
        Save a new job to this instance.

        :param id: job id
        :type id: int
        :param data: metadata
        :type data: dict
        :param output: raw output
        :type output: bytes
        """
        assert (type(data) == dict)
        assert ('result' in data.keys())
        insert = {}
        start = 0
        length = 0
        if len(output) > 0:
            # we consider the raw cursor to always be at the end of the file
            # maybe lock the following to be atomic ?
            start = self._rawout.tell()
            length = self._rawout.write(self.MAGIC_TOKEN.encode("utf-8"))
            length += self._rawout.write(output)

            insert = {
                'file': self.rawdata_prefix,
                'offset': start,
                'length': length
            }

        else:
            insert = {
                'file': "",
                'offset': -1,
                'length': 0
            }

        data['result']['output'] = insert

        assert (id not in self._data.keys())
        self._data[id] = data
        self._cnt += 1
        self._sz = max(start+length, self._sz + len(json.dumps(data)))

        if self._cnt % 10 == 0:
            self.flush()

    def load(self):
        """
        Load job data from disk to populate the cache.
        """
        with open(self._metadata_file, "r") as fh:
            # when reading metdata_file,
            # convert string-based keys to int (as managed by Python)
            content = json.load(fh)
            self._data = {k: v for k, v in content.items()}

    @property
    def content(self):
        for name, data in self._data.items():
            elt = Test()
            elt.from_json(data)
            
            offset = data['result']['output']['offset']
            length = data['result']['output']['length']
            if offset >= 0 and length > 0:
                elt.encoded_output = self.extract_output(offset, length)
            yield elt
    
    def extract_output(self, offset, length) -> str:
        assert(offset >= 0)
        assert(length > 0)
        
        self._rawout_reader.seek(offset)
        rawout = self._rawout_reader.read(length).decode('utf-8')
                
        if not rawout.startswith(self.MAGIC_TOKEN):
            raise PublisherException.BadMagicTokenError()
        
        return rawout[len(self.MAGIC_TOKEN):]
    
    def retrieve_test(self, id=None, name=None) -> List[Test]:
        """
        Find jobs based on its id or name and return associated Test object.
        
        Only id OR name should be set (not both). To handle multiple matches,
        this function returns a list of class:`Test`.

        :param id: job id, defaults to None
        :type id: int, optional
        :param name: test name (full), defaults to None
        :type name: str, optional
        :return: A list of class:`Test`
        :rtype: list
        """
        if (id is None and name is None) or \
                (id is not None and name is not None):
            raise PublisherException.UnknownJobError(id, name)

        lookup_table = []
        if id is not None:
            if id not in self._data:
                return []
            else:
                lookup_table = [self._data[id]]
        elif name is not None:
            lookup_table = list(
                filter(lambda x: name in x['id']['fq_name'], self._data.values()))

        res = []
        for elt in lookup_table:
            offset = elt['result']['output']['offset']
            length = elt['result']['output']['length']
            rawout = ""
            if length > 0:
                assert elt['result']['output']['file'] in self.rawdata_prefix
                rawout = self.extract_output(offset, length)

            eltt = Test()
            eltt.from_json(elt)
            eltt.encoded_output = rawout
            res.append(eltt)

        return res

    @property
    def size(self):
        """
        Current rawdata size

        :return: lenght of the rawdata file.
        :rtype: int
        """
        return self._sz

    @property
    def count(self):
        """
        Get the number of jobs in this handler.

        :return: job count
        :rtype: int
        """
        return self._cnt

    @property
    def prefix(self):
        """
        Getter to the build prefix

        :return: build prefix
        :rtype: str
        """
        return self._fileprefix

    @property
    def metadata_prefix(self):
        """
        Getter to the actual metadata file name

        :return: filename
        :rtype: str
        """
        return "{}.json".format(self._fileprefix)

    @property
    def rawdata_prefix(self):
        """
        Getter to the actual rawdata file name
        

        :return: file name
        :rtype: str
        """
        return "{}.bz2".format(self._fileprefix)


class ResultFileManager:
    """
    Manages multiple class:`ResultFile`. Main purpose is to manage files to
    ensure files stored on disk remain consistent.
    """
    increment = 0
    file_format = "jobs-{}"

    @classmethod
    def _ret_state_split_dict(cls):
        """
        initialize a default dict view with targeted statuses.

        :return: _description_
        :rtype: _type_
        """
        ret = {}
        ret.setdefault(str(Test.State.FAILURE), [])
        ret.setdefault(str(Test.State.SUCCESS), [])
        ret.setdefault(str(Test.State.ERR_DEP), [])
        ret.setdefault(str(Test.State.ERR_OTHER), [])
        return ret

    def discover_result_files(self) -> None:
        """
        Load existing results from prefix.
        """
        l = list(
            filter(lambda x: x.startswith('jobs-') and x.endswith(".json"),
                   os.listdir(self._outdir)
                   )
        )
        if len(l) > 0:
            curfile = None
            for f in list(map(lambda x: os.path.join(self._outdir, x), l)):
                p = os.path.dirname(f)
                f = os.path.splitext(os.path.basename(f))[0]
                curfile = ResultFile(p, f)
                curfile.load()
                self._opened_files[f] = curfile

            self._current_file = curfile

    def build_bidir_map_data(self) -> None:
        """
        Rebuild global views from partial storage on disk.
        
        For optimization reasons, information that may be rebuilt are not stored
        on disk to save space.
        """
        if not self._mapdata:
            return

        for fic, jobs in self._mapdata.items():
            for job in jobs:
                self._mapdata_rev[job] = fic

    def reconstruct_map_data(self) -> None:
        for job in self.browse_tests():
            self._mapdata_rev[job.id] = job.output_info['file']
            self._mapdata.setdefault(job.output_info['file'], list())
            self._mapdata[job.output_info['file']].append(id)
    
    def reconstruct_view_data(self) -> None:
        for job in self.browse_tests():
            state = str(job.state)
            id = job.jid
            self._viewdata['status'][state].append(id)
            for tag in job.tags:
                if tag not in self._viewdata['tags']:
                    self.register_view_item(view='tags', item=tag)
                self._viewdata['tags'][tag][state].append(id)

            self.register_view_item('tree', job.label)
            self._viewdata['tree'][job.label][state].append(id)
            if job.subtree:
                nodes = job.subtree.split('/')
                nb_nodes = len(nodes)
                for i in range(1, nb_nodes+1):
                    name = "/".join([job.label] + nodes[:i])
                    self.register_view_item('tree', name)
                    self._viewdata['tree'][name][state].append(id)

    def __init__(self, prefix=".", per_file_max_ent=0, per_file_max_sz=0) -> None:
        """
        Initialize a new instance to manage results in a build directory.

        :param prefix: result directory, defaults to "."
        :type prefix: str, optional
        :param per_file_max_ent: max number of tests per output file, defaults
            t(o unlimited (0)
        :type per_file_max_ent: int, optional
        :param per_file_max_sz: max size (bytes) for a single file, defaults to unlimited
        :type per_file_max_sz: int, optional
        """
        self._current_file = None
        self._outdir = prefix
        self._opened_files: Dict[ResultFile] = dict()

        map_filename = os.path.join(prefix, 'maps.json')
        view_filename = os.path.join(prefix, 'views.json')

        def preload_if_exist(path, default) -> dict:
            """
            Internal function: populate a file if found in dest dir.

            :param path: file to load
            :type path: str
            :param default: default value if file not found
            :type default: Any
            :return: the dict mapping the data
            :rtype: dict
            """
            if os.path.isfile(path):
                with open(path, 'r') as fh:
                    try:
                        return json.load(fh)
                    except:
                        return {}
            else:
                return default

        self._mapdata = preload_if_exist(map_filename, {})
        self._mapdata_rev = {}
        self._viewdata = preload_if_exist(view_filename, {
            'status': self._ret_state_split_dict(),
        })

        self._max_entries = per_file_max_ent
        self._max_size = per_file_max_sz

        self.build_bidir_map_data()
        
        self.discover_result_files()
        if not self._current_file:
            self.create_new_result_file()

        # the state view's layout is special, create directly from definition
        # now create basic view as well through the proper API
        self.register_view('tags')
        self.register_view_item(view='tags', item='compilation')

        self.register_view('tree')

    def save(self, job: Test):
        """
        Add a new job to be saved to the result directory.
        
        May not be flushed righ away to disk, some caching may be used to
        improve performance. While adding the Test to low-level manager, this
        function also updates view & maps accordingly.

        :param job: the job element to store
        :type job: class:`Test`
        """
        id = job.jid
        if id in self._mapdata.keys():
            raise PublisherException.AlreadyExistJobError(job.name)

        # create a new file if the current one is 'large' enough
        if (self._current_file.size >= self._max_size and self._max_size) or \
           (self._current_file.count >= self._max_entries and self._max_entries):
            self.create_new_result_file()

        # save info to file
        self._current_file.save(id, job.to_json(), job.encoded_output)

        # register this location from the map-id table
        self._mapdata_rev[id] = self._current_file.prefix
        assert self._current_file.prefix in self._mapdata
        self._mapdata[self._current_file.prefix].append(id)
        # record this save as a FAILURE/SUCCESS statistic for multiple views
        state = str(job.state)
        self._viewdata['status'][state].append(id)
        for tag in job.tags:
            if tag not in self._viewdata['tags']:
                self.register_view_item(view='tags', item=tag)
            self._viewdata['tags'][tag][state].append(id)

        self.register_view_item('tree', job.label)
        self._viewdata['tree'][job.label][state].append(id)
        if job.subtree:
            nodes = job.subtree.split('/')
            nb_nodes = len(nodes)
            for i in range(1, nb_nodes+1):
                name = "/".join([job.label] + nodes[:i])
                self.register_view_item('tree', name)
                self._viewdata['tree'][name][state].append(id)

    def retrieve_test(self, id) -> Optional[Test]:
        """
        Build the Test object mapped to the given job id.
        
        If such ID does not exist, it will return None.

        :param id: _description_
        :type id: _type_
        :return: _description_
        :rtype: List[Test]
        """
        if id not in self._mapdata_rev:
            return None
        filename = self._mapdata_rev[id]
        handler = None
        if filename == self._current_file.metadata_prefix:
            handler = self._current_file
        elif filename in self._opened_files:
            handler = self._opened_files[filename]
        else:
            handler = ResultFile(self._outdir, filename)
            self._mapdata[filename] = handler

        res = handler.retrieve_test(id=id)
        if res:
            if len(res) > 1:
                raise CommonException.UnclassifiableError(
                    reason="Given info leads to more than one job",
                    dbg_info={
                        "data": id,
                        'matches': res
                    }
                )
            else:
                return res[0]
        else:
            return None

    def browse_tests(self) -> Iterable[Test]:
        """
        Iterate over every job stored into this build directory.

        :return: an iterable of Tests
        :rtype: List of tests
        :yield: Test
        :rtype: Iterator[Test]
        """
        for hdl in self._opened_files.values():
            for j in hdl.content:
                yield j
            
    def retrieve_tests_by_name(self, name) -> List[Test]:
        """
        Locate a test by its name.
        
        As multiple matches could occur, this function return a list of class:`Test`

        :param name: the test name
        :type name: str
        :return: the actual list of test, empty if no one is found
        :rtype: list
        """
        ret = []
        for hdl in self._opened_files.values():
            ret += hdl.retrieve_test(name=name)
        return ret

    def register_view(self, name) -> None:
        """
        Initialize a new view for this result manager.

        :param name: the view name
        :type name: str
        """
        self._viewdata.setdefault(name, {})

    def register_view_item(self, view, item) -> None:
        """
        Initialize a single item within a view.

        :param view: the view name (created if not exist)
        :type view: str
        :param item: the item
        :type item: str
        """
        if view not in self._viewdata:
            self.register_view(view)

        self._viewdata[view].setdefault(item, self._ret_state_split_dict())

    def create_new_result_file(self) -> None:
        """
        Initialize a new result file handler upon request.
        """
        filename = self.file_format.format(ResultFileManager.increment)
        ResultFileManager.increment += 1
        self._current_file = ResultFile(self._outdir, filename)
        self._opened_files[filename] = self._current_file
        self._mapdata.setdefault(self._current_file.prefix, list())

    def flush(self) -> None:
        """
        Ensure everything is in sync with persistent storage.
        """
        if self._current_file:
            self._current_file.flush()

        with open(os.path.join(self._outdir, "maps.json"), "w") as fh:
            json.dump(self._mapdata, fh)

        with open(os.path.join(self._outdir, "views.json"), 'w') as fh:
            json.dump(self._viewdata, fh)

    @property
    def views(self):
        """
        Returns available views for the current instance.

        :return: the views
        :rtype: dict
        """
        return self._viewdata

    @property
    def maps(self):
        """
        Returns available views from the current instance.

        :return: the maps
        :rtype: dict
        """
        return self._mapdata

    @property
    def total_cnt(self):
        """
        Returns the total number of jobs from that directory (=run).

        :return: number of jobs
        :rtype: int
        """
        return len(self._mapdata_rev.keys())

    def map_id(self, id):
        """
        Comnvert a job ID into its class:`Test` representation.

        :param id: job id
        :type id: int
        :return: the associated Test object or None if not found
        :rtype: class:`Test` or None
        """
        if id not in self._mapdata_rev:
            return None
        res = self._mapdata_rev[id]
        # if the mapped object is already resolved:
        if isinstance(res, Test):
            return res

        if res not in self._opened_files:
            self._opened_files[res] = ResultFile(self._outdir, res)
        hdl = self._opened_files[res]
        
        match = hdl.retrieve_test(id=id)
        assert (len(match) <= 1)
        if match:
            # cache the mapping
            self._mapdata_rev[id] = match[0]
            return match[0]
        else: 
            return None

    @property
    def status_view(self):
        """
        Returns the status view provided by PCVS.

        :return: a view
        :rtype: dict
        """
        return self._viewdata['status']

    @property
    def tags_view(self):
        """
        Get the tags view provided by PCVS.

        :return: a view
        :rtype: dict
        """
        return self._viewdata['tags']

    @property
    def tree_view(self):
        """
        Get the tree view, provided by default.

        :return: a view
        :rtype: dict
        """
        return self._viewdata['tree']

    def subtree_view(self, subtree):
        """
        Get a subset of the 'tree' view. Any LABEL/subtree combination is valid.

        :param subtree: the prefix to look for
        :type subtree: str
        :return: the dict mapping tests to the request
        :rtype: dict
        """
        if subtree not in self._viewdata['tree']:
            return None
        return self._viewdata['tree'][subtree]

    def finalize(self):
        """
        Flush & close the current manager.
        
        This instance should not be used again after this call.
        """
        self.flush()
        if self._current_file:
            self._current_file.close()

        for f in self._opened_files.values():
            f.close()


class BuildDirectoryManager:
    """
    This class is intended to serve a build directory from a single entry
    point. Any module requiring to deal with resources from a run should be
    compliant with this interface. It provides basic mechanism to load/save any
    past, present or future executions.
    """
    def __init__(self, build_dir="."):
        """
        Initialize a new instance.
        
        This is not destructive, it won't delete any existing resource created
        from previous execution. It will mainly flag this directory as a valid
        PCVS build directory.

        :param build_dir: the build dir, defaults to "."
        :type build_dir: str, optional
        """
        if not os.path.isdir(build_dir):
            raise CommonException.NotFoundError(
                reason="Invalid build directory, should exist *before* init.",
                dbg_info={"build prefix": build_dir}
            )

        self._path = build_dir
        self._extras = list()
        self._results = None
        self._config = None
        self._scratch = os.path.join(build_dir, pcvs.NAME_BUILD_SCRATCH)
        old_archive_dir = os.path.join(build_dir, pcvs.NAME_BUILD_ARCHIVE_DIR)

        open(os.path.join(self._path, pcvs.NAME_BUILDFILE), 'w').close()

        if not os.path.isdir(old_archive_dir):
            os.makedirs(old_archive_dir)

    def init_results(self, per_file_max_sz=0):
        """
        Initialize the result handler. 
        
        This function is not called directly from the __init__ method as this
        isntance may be used for both reading & writing into the destination
        directory. This function implies storing a new execution.

        :param per_file_max_sz: max file size, defaults to unlimited
        :type per_file_max_sz: int, optional
        """
        resdir = os.path.join(self._path, pcvs.NAME_BUILD_RESDIR)
        if not os.path.exists(resdir):
            os.makedirs(resdir)

        self._results = ResultFileManager(prefix=resdir,
                                          per_file_max_sz=per_file_max_sz)

    @property
    def results(self):
        """
        Getter to the result handler, for direct access

        :return: the result handler
        :rtype: class:`ResultFileManager`
        """
        return self._results

    @property
    def prefix(self):
        """
        Get the build directory prefix

        :return: the build path
        :rtype: str
        """
        return self._path

    def prepare(self, reuse=False):
        """
        Prepare the dir for a new run.
        
        This function is not included as part of the __init__ function as this
        instance may be used both for reading & writing into the destination
        directory. This function implies all previous results be be cleared off.

        :param reuse: keep previously generated YAML test-files, defaults to False
        :type reuse: bool, optional
        """
        if not reuse:
            self.clean(pcvs.NAME_BUILD_SCRATCH)
        self.clean(pcvs.NAME_BUILD_RESDIR)
        self.clean(pcvs.NAME_BUILD_CONF_FN)
        self.clean(pcvs.NAME_BUILD_CONF_SH)
        self.clean(pcvs.NAME_BUILD_CACHEDIR)
        self.clean(pcvs.NAME_BUILD_CONTEXTDIR)

        self.clean_archives()
        
        self.save_extras(pcvs.NAME_BUILD_CACHEDIR, dir=True, export=False)
        self.save_extras(pcvs.NAME_BUILD_CONTEXTDIR, dir=True, export=False)
        self.save_extras(pcvs.NAME_BUILD_SCRATCH, dir=True, export=False)

    @property
    def sid(self) -> Optional[int]:
        """
        Return the run ID as per configured with the current build directory.

        If not found, this function may return None

        :return: the session ID
        :rtype: int
        """
        if self._config.validation.sid:
            return self._config.validation.sid
        else:
            return None

    def load_config(self):
        """
        Load config stored onto disk & populate the current instance.

        :return: the loaded config
        :rtype: class:`MetaConfig`
        """
        with open(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN), 'r') as fh:
            self._config = MetaConfig(YAML(typ='safe').load(fh))

        return self._config
    def use_as_global_config(self):
        MetaConfig.root = self._config
        
    def save_config(self, config) -> None:
        """
        Save the config & store it directly into the build directory.

        :param config: config
        :type config: class:`MetaConfig`
        """
        if not isinstance(config, MetaConfig):
            config = MetaConfig(config)
        self._config = config
        with open(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN), 'w') as fh:
            h = YAML(typ='safe')
            h.default_flow_style = None
            h.dump(config.dump_for_export(), fh)
    

    def get_config(self) -> dict:
        """
        Return the loaded configuration for the current build directory.

        :return: a dict representantion of yaml config
        :rtype: dict
        """
        return self._config
        
    @property
    def config(self) -> MetaConfig:
        """
        Return the configuation associated with the current build directory

        :return: config struct
        :rtype: class:`MetaConfig`
        """
        return self._config

    def add_cache_entry(self, idx=0):
        d = os.path.join(self._path, pcvs.NAME_BUILD_CONTEXTDIR, str(idx))
        
        if os.path.exists(d):
            raise CommonException.AlreadyExistError(d)
        else:
            os.makedirs(d)
        
        return d
    
    def get_cache_entry(self, idx=0):
        return os.path.join(self._path, pcvs.NAME_BUILD_CONTEXTDIR, str(idx))
    

    def save_extras(self, rel_filename, data="", dir=False, export=False) -> None:
        """
        Register a specific build-relative path, to be saved into the directory.
        
        The only entry-point to save a resource into it. Resources can be files
        (with or without content) or directory.
        
        If `export` is set to True, resource (file or whole directory) will also
        be copied to the final archive.

        :param rel_filename: the filepath, relative to build dir.
        :type rel_filename: str
        :param data: data to be saved into the target file, defaults to ""
        :type data: Any, optional
        :param dir: is it a directory to save, defaults to False
        :type dir: bool, optional
        :param export: should the target be also exported in final archive, defaults to False
        :type export: bool, optional
        """
        if os.path.isabs(rel_filename):
            raise CommonException.UnclassifiableError(
                reason="Extras should be saved as relative paths",
                dbg_info={"filename": rel_filename})

        if dir:
            try:
                os.makedirs(os.path.join(self._path, rel_filename))
            except FileExistsError:
                io.console.warn("subprefix {} existed before registering".format(rel_filename))
        else:
            d = os.path.dirname(rel_filename)
            if not os.path.isdir(d):
                os.makedirs(d)

            with open(os.path.join(self._path, rel_filename), 'w') as fh:
                fh.write(data)

        if export:
            self._extras.append(rel_filename)

    def clean(self, *args) -> None:
        """
        Prepare the build directory for a new execution by removing anything not
        relevant for a new run.
        
        Please not this function will erase anything not relative to PCVS. As an
        argument, one may specify a specific prefix to be removed. Paths should
        relative to root build directory.
        """
        assert (utils.check_is_buildir(self._path))

        def proper_clean(p):
            if os.path.isfile(p) or os.path.islink(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        if args:
            for p in args:

                proper_clean(os.path.join(self._path, p))
        else:
            for f in os.listdir(self._path):
                current = os.path.join(self._path, f)
                if not utils.check_is_archive(current):
                    shutil.rmtree(current)

    def clean_archives(self) -> None:
        """
        Prepare the build directory for a new execution by moving any previous
        archive to the backup directory named after NAME_BUILD_ARCHIVE_DIR.
        """
        assert (utils.check_is_buildir(self._path))
        for f in os.listdir(self._path):
            current = os.path.join(self._path, f)
            if utils.check_is_archive(current):
                shutil.move(current,
                            os.path.join(self._path, pcvs.NAME_BUILD_ARCHIVE_DIR, f))

    def create_archive(self, timestamp=None) -> str:
        """
        Generate an archive for the build directory.
        
        This archive will be stored in the root directory..

        :param timestamp: file suffix, defaults to current timestamp
        :type timestamp: Datetime, optional
        :return: the archive path name
        :rtype: str
        """
        
        #ensure all results are flushed away before creating the archive
        self.results.finalize()
        
        if not timestamp:
            timestamp = datetime.datetime.now()
        str_timestamp = timestamp.strftime('%Y%m%d%H%M%S')
        archive_file = os.path.join(
            self._path,
            "pcvsrun_{}.tar.gz".format(str_timestamp)
        )
        archive = tarfile.open(archive_file, mode='w:gz')

        def __relative_add(path, recursive=False):
            archive.add(path,
                        arcname=os.path.join("pcvsrun_{}".format(str_timestamp),
                                             os.path.relpath(path, self._path)),
                        recursive=recursive)

        # copy results
        __relative_add(os.path.join(self._path, pcvs.NAME_BUILD_RESDIR),
                    recursive=True)
        # copy the config
        __relative_add(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN))
        __relative_add(os.path.join(self._path, pcvs.NAME_DEBUG_FILE))

        not_found_files = list()
        for p in self._extras:
            if not os.path.exists(p):
                not_found_files.append(p)
            __relative_add(p)
            
        if len(not_found_files) > 0:
            raise CommonException.NotFoundError(
                    reason="Extra files to be stored to archive do not exist",
                    dbg_info={"Failed paths": not_found_files}
                )

        archive.close()
        return archive_file

    @classmethod
    def load_from_archive(cls, archive_path):
        """
        Populate the instance from an archive.
        
        This object is initially built to load data from a build directory. This
        way, the object is mapped with an existing archive.
        
        .. warning::
            This method does not support (yet) to save tests after an archive has
            been loaded (as no output directory has been configured).

        :param archive_path: _description_
        :type archive_path: _type_
        :return: _description_
        :rtype: _type_
        """
        archive = tarfile.open(archive_path, mode="r:gz")
        
        path = tempfile.mkdtemp(prefix="pcvs-archive")
        archive.extractall(path)
        archive.close()
        
        d = [x for x in os.listdir(path) if x.startswith("pcvsrun_")]
        assert(len(d) == 1)
        hdl = BuildDirectoryManager(build_dir=os.path.join(path, d[0]))
        hdl.load_config()
        return hdl

    def finalize(self):
        """
        Close & release the current instance.
        
        It should not be used to save tests after this call.
        """
        self.results.finalize()

    @property
    def scratch_location(self):
        """
        Returns where third-party artifacts must be stored

        :return: the scratch directory
        :rtype: str
        """
        return self._scratch
