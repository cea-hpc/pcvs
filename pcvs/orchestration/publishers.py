import json
import os
import bz2

from ruamel.yaml import YAML
from typing import List, Optional

from pcvs import NAME_BUILD_RESDIR
from pcvs.testing.test import Test
from pcvs.helpers.system import MetaConfig
from pcvs.helpers.system import ValidationScheme
from pcvs.plugins import Plugin


class ResultFile:
    MAGIC_TOKEN = "PCVS-START-RAW-OUTPUT"
    MAX_RAW_SIZE = 10 * 1024 * 1024
    
    def __init__(self, filepath, filename, mode="w"):
        self._fileprefix = filename
        self._path = filepath
        self._cnt = 0
        self._mode = mode
        
        prefix = os.path.join(filepath, filename)
        self._metadata = open("{}.json".format(prefix), mode)
        self._rawout = bz2.open("{}.bz2".format(prefix), mode)
        
        if 'r' in mode:
            self._data = json.load(self._metadata)
        else:
            self._data = {}
        
    def __del__(self):
        self.close()
        
    def close(self):
        self.flush()
        if self._rawout:
            self._rawout.close()
        if self._metadata:
            self._metadata.close()
        
    def flush(self):
        if 'w' in self._mode:
            self._rawout.flush()
            json.dump(self._data, self._metadata)
            self._metadata.flush()
            # reset for the next flush() to erase the whole file
            self._metadata.seek(0)
                
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
        if "r" not in self._mode:
            raise Exception
        self._data = json.load(self._metadata)
        
    def retrieve_test(self, id=None, name=None) -> List[Test]:
        if not bool(id) ^ bool(name):
            raise Exception

        lookup_table = []
        if id:
            if id not in self._data:
                return []
            else:
                lookup_table = [self._data[id]]
        elif name:
                lookup_table = list(filter(lambda x: x['id']['fq_name'] == name, self._data.values()))
        
        res = []
        for elt in lookup_table:
            
            offset = elt['result']['output']['offset']
            length = elt['result']['output']['length']
            rawout = ""
            if offset >= 0:
                assert elt['result']['output']['file'] in self.rawdata_prefix
                self._rawout.seek(offset)
                rawout = self._rawout.read(length).decode('utf-8')
                if not rawout.startswith(self.MAGIC_TOKEN):
                    Exception

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
    def metadata_prefix(self):
        return "{}.json".format(self._fileprefix)
    
    @property
    def rawdata_prefix(self):
        return "{}.bz2".format(self._fileprefix)
        

class Publisher:
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

    def load_and_prepare_result_file(self):
        
        l = list(
                filter(lambda x: x.startswith('jobs-') and x.endswith(".json"),
                       os.listdir(self._outdir)
                    )
                 )
        if len(l) > 0:
            self.load_result_files(list(map(lambda x:os.path.join(self._outdir, x), l)))
        else:
            self.create_new_result_file()
        

    def __init__(self, prefix=".", per_file_max_ent=0, per_file_max_sz=0):
        
        self._current_file = None
        self._outdir = prefix
        
        map_filename = os.path.join(prefix, 'maps.json')
        view_filename = os.path.join(prefix, 'views.json')
    
        def preload_if_exist(path, default) -> dict:
            if os.path.isfile(path):
                with open(path, 'r') as fh:
                    return json.load(fh)
            else:
                return default
        
        self._mapdata = preload_if_exist(map_filename, {})
        self._viewdata = preload_if_exist(view_filename, {
            'status': self._ret_state_split_dict(),
        })
        
        self._mapfile = open(os.path.join(prefix, "maps.json"), "w")
        self._viewfile = open(os.path.join(prefix, "views.json"), 'w')
    
        self._max_entries = per_file_max_ent
        self._max_size = per_file_max_sz
        
        self.load_and_prepare_result_file()
        
        #the state view's layout is special, create directly from definition
        #now create basic view as well through the proper API
        self.register_view('tags')
        self.register_view_item(view='tags', item='compilation')
        
        self.register_view('tree')
        
    def load_result_files(self, list_of_files):
        for f in list_of_files:
            p = os.path.dirname(f)
            f = os.path.splitext(os.path.basename(f))[0]
            self._current_file = ResultFile(p, f, mode='r')
        
    def retrieve_test(self, id) -> List[Test]:
        str_id = str(id)
        if str_id not in self._mapdata:
            return None
        
        filename = self._mapdata[str_id]
        handler = None
        if filename == self._current_file.metadata_prefix:
            handler = self._current_file
        else:
            handler = ResultFile(os.path.splitext(filename)[0], mode='r')
            
        return handler.retrieve_test(str_id)
    
    def browse_tests(self) -> Test:
        for test_id in self._mapdata:
            l = self.retrieve_test(test_id)
            assert(len(l) == 1)
            yield l[0]
    
    def retrieve_tests_by_name(self, name) -> List[Test]:
        res = []
        for f in list(
                    filter(lambda x: x.startswith('jobs-') and x.endswith(".json"),
                       os.listdir(self._outdir))):
            hdl = ResultFile(self._outdir, os.path.splitext(f)[0], mode='r')
            ret = hdl.retrieve_test(name=name)
            if ret:
                res.append(*ret)
            del hdl
        return res
    
    def register_view(self, name):
        self._viewdata.setdefault(name, {})
    
        
    def register_view_item(self, view, item):
        if view not in self._viewdata:
            self.register_view(view)
        
        self._viewdata[view].setdefault(item, self._ret_state_split_dict())
        
    def test_view_item(self, view, item) -> bool:
        return item in self._viewdata[view]
    
    def create_new_result_file(self):
        if self._current_file:
            del self._current_file
        
        filename = self.file_format.format(Publisher.increment)
        Publisher.increment += 1
        self._current_file = ResultFile(self._outdir, filename)
        
    def save(self, job: Test):
        str_id = str(job.jid)
        if str_id in self._mapdata.keys():
            raise Exception
        
        # create a new file if the current one is 'large' enough
        if (self._current_file.size >= self._max_size and self._max_size) or \
           (self._current_file.count >= self._max_entries and self._max_entries):
            self.create_new_result_file()
        
        # save info to file
        self._current_file.save(str_id, job.to_json(), job.encoded_output)
        
        # register this location from the map-id table
        self._mapdata[str_id] = self._current_file.metadata_prefix
        # record this save as a FAILURE/SUCCESS statistic for multiple views
        state = str(job.state)
        self._viewdata['status'][state].append(str_id)
        for tag in job.tags:
            self._viewdata['tags'][tag][state].append(str_id)
        
        self.register_view_item('tree', job.label)
        self._viewdata['tree'][job.label][state].append(str_id)
        if job.subtree:
            nodes = job.subtree.split('/')
            nb_nodes = len(nodes)
            for i in range(1, nb_nodes+1):
                name = "/".join([job.label] + nodes[:i])
                self.register_view_item('tree', name)
                self._viewdata['tree'][name][state].append(str_id)
            
    def __del__(self):
        self.finalize()
        
    def flush(self):
        if self._current_file:
            self._current_file.flush()
        json.dump(self._mapdata, self._mapfile)
        json.dump(self._viewdata, self._viewfile)
        self._mapfile.seek(0)
        self._viewfile.seek(0)
        
    def finalize(self):
        self.flush()
        if self._current_file:
            self._current_file.close()
