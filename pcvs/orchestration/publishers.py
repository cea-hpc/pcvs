import os
import json
import pprint

class Publisher:
    increment = 0

    def __init__(self, prefix="."):
        filename = "pcvs_rawdat{:>04d}.json".format(self.increment)
        self._layout = {
            "tests": []
        }
        self._destpath = os.path.join(prefix, filename)

    def add_test_entry(self, json):
        self._layout['tests'].append(json)
        
    def finalize(self):
        assert(os.path.isdir(os.path.dirname(self._destpath)))
        with open(self._destpath, 'w+') as fh:
            json.dump(self._layout, fh)