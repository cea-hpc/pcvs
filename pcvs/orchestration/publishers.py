import json
import os

from pcvs import NAME_BUILD_RESDIR


class Publisher:
    increment = 0
    fn_fmt = "pcvs_rawdat{:>04d}.json"
    
    def __init__(self, prefix="."):
        
        self._layout = {
            "tests": []
        }
        self._destpath = os.path.join(prefix, NAME_BUILD_RESDIR)
        assert(os.path.isdir(self._destpath))

    def empty_entries(self):
        self._layout['tests'] = list()

    def add(self, json):
        self._layout['tests'].append(json)
        
    def flush(self):
        # nothing to flush since the last call
        if len(self._layout['tests']) <= 0:
            return
        
        filename = os.path.join(self._destpath, self.fn_fmt.format(Publisher.increment))
        assert(not os.path.isfile(filename))
        
        Publisher.increment += 1
        
        with open(filename, 'w+') as fh:
            json.dump(self._layout, fh)
            self.empty_entries()