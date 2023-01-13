import shutil
import tempfile
import bz2
import json
import os
from typing import List, Optional, Dict
import datetime
import tarfile

from ruamel.yaml import YAML

import pcvs
from pcvs.helpers import utils
from pcvs.helpers.system import MetaConfig, ValidationScheme
from pcvs.plugins import Plugin
from pcvs.testing.test import Test


class ResultFile:
    MAGIC_TOKEN = "PCVS-START-RAW-OUTPUT"
    MAX_RAW_SIZE = 10 * 1024 * 1024
    
    def __init__(self, filepath, filename, mode="r"):
        self._fileprefix = filename
        self._path = filepath
        self._cnt = 0
        self._data = {}
        
        prefix = os.path.join(filepath, filename)
        
        #R/W access & seek to the start of the file
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
        self.flush()
        if self._rawout:
            self._rawout.close()
            self._rawout = None

    def flush(self):
        with open(self._metadata_file, "w") as fh:
            json.dump(self._data, fh)

        if self._rawout:
            self._rawout.flush()
                
    def save(self, id, data, output):
        assert(type(data) == dict)
        assert('result' in data.keys())
        insert = {}
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
                'file': None,
                'offset': -1,
                'length': 0
            }
            
             
        data['result']['output'] = insert
        
        assert(id not in self._data.keys())
        self._data[id] = data
        self._cnt += 1
        
        if self._cnt % 10 == 0:
            self.flush()

    def load(self):
        with open(self._metadata_file, "r") as fh:
            # when reading metdata_file,
            # convert string-based keys to int (as managed by Python)
            content = json.load(fh)
            self._data = {int(k): v for k, v in content.items()}
        
    def retrieve_test(self, id=None, name=None) -> List[Test]:
        if (id is None and name is None) or \
            (id is not None and name is not None):
            raise Exception()
        
        lookup_table = []
        if id is not None:
            if id not in self._data:
                return []
            else:
                lookup_table = [self._data[id]]
        elif name is not None:
                lookup_table = list(filter(lambda x: name in x['id']['fq_name'], self._data.values()))
        
        res = []
        for elt in lookup_table:
            offset = elt['result']['output']['offset']
            length = elt['result']['output']['length']
            rawout = ""
            if offset >= 0:
                assert elt['result']['output']['file'] in self.rawdata_prefix
                self._rawout_reader.seek(offset)
                rawout = self._rawout_reader.read(length).decode('utf-8')
                if not rawout.startswith(self.MAGIC_TOKEN):
                    raise Exception()

                rawout = rawout[len(self.MAGIC_TOKEN):]

            elt['result']['output']['raw'] = rawout
            
            eltt = Test()
            eltt.from_json(elt)
            res.append(eltt)

        return res
        
    @property
    def size(self):
        return self._rawout.tell()
    
    @property
    def count(self):
        return self._cnt
    
    @property
    def prefix(self):
        return self._fileprefix
    @property
    def metadata_prefix(self):
        return "{}.json".format(self._fileprefix)
    
    @property
    def rawdata_prefix(self):
        return "{}.bz2".format(self._fileprefix)

class ResultFileManager:
    increment = 0
    file_format = "jobs-{}"
    
    @classmethod
    def _ret_state_split_dict(cls):
        ret = {}
        ret.setdefault(str(Test.State.FAILURE), [])
        ret.setdefault(str(Test.State.SUCCESS), [])
        ret.setdefault(str(Test.State.ERR_DEP), [])
        ret.setdefault(str(Test.State.ERR_OTHER), [])
        return ret

    def discover_result_files(self):
        l = list(
                filter(lambda x: x.startswith('jobs-') and x.endswith(".json"),
                       os.listdir(self._outdir)
                    )
                 )
        if len(l) > 0:
            curfile = None
            for f in list(map(lambda x : os.path.join(self._outdir, x), l)):
                p = os.path.dirname(f)
                f = os.path.splitext(os.path.basename(f))[0]
                curfile = ResultFile(p, f)
                self._opened_files[f] = curfile
            
            self._current_file = curfile
    
    def reconstruct_map_data(self):
        if not self._mapdata:
            return
        
        for fic, jobs in self._mapdata.items():
            for job in jobs:
                self._mapdata_rev[job] = fic

    def __init__(self, prefix=".", per_file_max_ent=0, per_file_max_sz=0):
        
        self._current_file = None
        self._outdir = prefix
        self._opened_files: Dict[ResultFile] = dict()
        
        map_filename = os.path.join(prefix, 'maps.json')
        view_filename = os.path.join(prefix, 'views.json')
        
        def preload_if_exist(path, default) -> dict:
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
        
        self.reconstruct_map_data()
        
        self.discover_result_files()
        if not self._current_file:
            self.create_new_result_file()
        
        #the state view's layout is special, create directly from definition
        #now create basic view as well through the proper API
        self.register_view('tags')
        self.register_view_item(view='tags', item='compilation')
        
        self.register_view('tree')
        
    def save(self, job: Test):
        id = job.jid
        if id in self._mapdata.keys():
            raise Exception
        
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
                
    def retrieve_test(self, id) -> List[Test]:
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
            
        return handler.retrieve_test(id=id)
    
    def browse_tests(self) -> Test:
        for test_id in self._mapdata:
            l = self.retrieve_test(test_id)
            assert(len(l) == 1)
            yield l[0]
    
    def retrieve_tests_by_name(self, name) -> List[Test]:
        ret = []
        for hdl in self._opened_files.values():
            ret += hdl.retrieve_test(name=name)
        return ret
    
    def register_view(self, name):
        self._viewdata.setdefault(name, {})
        
    def register_view_item(self, view, item):
        if view not in self._viewdata:
            self.register_view(view)
        
        self._viewdata[view].setdefault(item, self._ret_state_split_dict())
        
    def test_view_item(self, view, item) -> bool:
        return item in self._viewdata[view]
    
    def create_new_result_file(self):
        filename = self.file_format.format(ResultFileManager.increment)
        ResultFileManager.increment += 1
        self._current_file = ResultFile(self._outdir, filename)
        self._opened_files[filename] = self._current_file
        self._mapdata.setdefault(self._current_file.prefix, list())

    def flush(self):
        if self._current_file:
            self._current_file.flush()
        
        with open(os.path.join(self._outdir, "maps.json"), "w") as fh:
            json.dump(self._mapdata, fh)
        
        with open(os.path.join(self._outdir, "views.json"), 'w') as fh:
            json.dump(self._viewdata, fh)

    @property
    def views(self):
        return self._viewdata

    @property
    def maps(self):
        return self._mapdata
    
    @property
    def total_cnt(self):
        return len(self._mapdata_rev.keys())
    
    def map_id(self, id):

        if id not in self._mapdata_rev:
            return None
        f = self._mapdata_rev[id]
        if f not in self._opened_files:
            self._opened_files[f] = ResultFile(self._outdir, f)
        hdl = self._opened_files[f]
        match = hdl.retrieve_test(id=id)
        
        assert(len(match) <= 1)
        return match[0]

    @property
    def status_view(self):
        return self._viewdata['status']
    
    @property
    def tags_view(self):
        return self._viewdata['tags']
    
    @property
    def tree_view(self):
        return self._viewdata['tree']
    
    def subtree_view(self, subtree):
        if subtree not in self._viewdata['tree']:
            return None
        return self._viewdata['tree'][subtree]
    
    def finalize(self):
        self.flush()
        if self._current_file:
            self._current_file.close()
            
        for f in self._opened_files.values():
            f.close()


class BuildDirectoryManager:
    def __init__(self, build_dir="."):
        if not os.path.isdir(build_dir):
            raise Exception()
        
        self._path = build_dir
        self._extras = list()
        self._results = None
        self._scratch = os.path.join(build_dir, pcvs.NAME_BUILD_SCRATCH)
        old_archive_dir = os.path.join(build_dir, pcvs.NAME_BUILD_ARCHIVE_DIR)
        
        open(os.path.join(self._path, pcvs.NAME_BUILDFILE), 'w').close()
        
        if not os.path.isdir(old_archive_dir):
            os.makedirs(old_archive_dir)
            
    
    def init_results(self, per_file_max_sz=0):
        resdir = os.path.join(self._path, pcvs.NAME_BUILD_RESDIR)
        if not os.path.exists(resdir):
            os.makedirs(resdir)
        
        self._results = ResultFileManager(prefix=resdir,
                                          per_file_max_sz=per_file_max_sz)

    @property
    def results(self):
        return self._results

    @property
    def prefix(self):
        return self._path
    
    def prepare(self, reuse=False):
        if not reuse:
            self.clean(pcvs.NAME_BUILD_SCRATCH)
        self.clean(pcvs.NAME_BUILD_RESDIR)
        self.clean(pcvs.NAME_BUILD_CONF_FN)
        self.clean('conf.env')

        self.clean_archives()
            
    @property
    def sid(self):
        if self._config.validation.sid:
            return self._config.validation.sid
        else:
            return None

    def load_config(self):
        
        with open(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN), 'r') as fh:
            self._config = MetaConfig(YAML(typ='safe').load(fh))

        return self._config
    
    def save_config(self, config):
        self._config = config
        with open(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN), 'w') as fh:
            YAML(typ='safe').dump(config, fh)
   
    @property
    def config(self):
        return self._config
        
    def save_extras(self, rel_filename, data="", dir=False, export=False):
        if os.path.isabs(rel_filename):
            raise Exception()
        
        if dir:
            os.makedirs(os.path.join(self._path, rel_filename))
        else:
            d = os.path.dirname(rel_filename)
            if not os.path.isdir(d):
                os.makedirs(d)
                
            with open(os.path.join(self._path, rel_filename), 'w') as fh:
              fh.write(data)
            
        if export:
            self._extras.append(rel_filename)
            
    def clean(self, *args):
        assert(utils.check_is_buildir(self._path))
        
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
    
    def clean_archives(self):
        assert(utils.check_is_buildir(self._path))
        for f in os.listdir(self._path):
            current = os.path.join(self._path, f)
            if utils.check_is_archive(current):
                shutil.move(current, 
                            os.path.join(self._path, pcvs.NAME_BUILD_ARCHIVE_DIR, f))
    

    def create_archive(self, timestamp=None) -> str:
        if not timestamp:
            timestamp = datetime.datetime.now()
        
        archive_file = os.path.join(
            self._path,
            "pcvsrun_{}.tar.gz".format(timestamp.strftime('%Y%m%d%H%M%S'))
        )
        archive = tarfile.open(archive_file, mode='w:gz')
        
        # copy results 
        archive.add(os.path.join(self._path, pcvs.NAME_BUILD_RESDIR), recursive=True)
        #copy the config
        archive.add(os.path.join(self._path, pcvs.NAME_BUILD_CONF_FN))
        archive.add(os.path.join(self._path, pcvs.NAME_DEBUG_FILE))
        
        for p in self._extras:
            if not os.path.exists(p):
                raise Exception()
            archive.add(p)
            
        archive.close()
        return archive_file
    
    @classmethod
    def load_from_archive(cls, archive_path):
        archive = tarfile.open(archive_path, mode="w:gz")
        
        path = tempfile.mkdtemp(prefix="pcvs-archive")
        archive.extractall(path)
        hdl =  BuildDirectoryManager(build_dir=path)
        hdl.load_config()
        return hdl
    
    def finalize(self):
        self.results.finalize()

    @property
    def scratch_location(self):
        return self._scratch
