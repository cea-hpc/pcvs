from pcvs.testing.test import Test
from pcvs.backend.session import Session

class DataRepresentation:
    def __init__(self):
        self.rootree = {}

    def __insert_in_tree(self, test, node, depth):
            assert('__metadata' in node.keys())
            
            node["__metadata"]["count"][int(test.state)] += 1
            
            if len(depth) == 0:
                #do something
                if '__elems' not in node:
                    node['__elems'] = list()
                node['__elems'].append(test)
            else:
                node.setdefault('__elems', {})
                node["__elems"].setdefault(depth[0],
                    {
                        "__metadata": {
                            "count": {k: 0 for k in list(map(int, Test.State))}
                        }
                    })
                self.__insert_in_tree(test, node["__elems"][depth[0]], depth[1:])
        
    def insert_session(self, sid, session_data):

        if sid in self.rootree.keys():
            while sid in self.rootree.keys():
                sid = random.randint(0, 10000)
            
        self.rootree.setdefault(sid, {
            "fs-tree": {
                        "__metadata": {
                            "count": {k: 0 for k in list(map(int, Test.State))}
                        }
                    },
            "tags": {
                        "__metadata": {
                            "count": {k: 0 for k in list(map(int, Test.State))}
                        }
                    },
            "iterators": {
                        "__metadata": {
                            "count": {k: 0 for k in list(map(int, Test.State))}
                        }
                    },
            "failures": {
                        "__metadata": {
                            "count": {k: 0 for k in list(map(int, Test.State))}
                        }
                    },
            "state": Session.State(session_data["state"]),
            "path": session_data["buildpath"]
        })

    def close_session(self, sid, session_data):
        assert(sid in self.rootree.keys())
        self.rootree[sid]["state"] = session_data["state"]

    def insert_test(self, sid, test: Test):
        # first, insert the test in the hierachy
        label = test.label
        subtree = test.subtree
        te_name = test.te_name
        
        sid_tree = self.rootree[sid]
        self.__insert_in_tree(test, sid_tree["fs-tree"], [label, subtree, te_name])
        
        for tag in test.tags:
            self.__insert_in_tree(test, sid_tree["tags"], [tag])
        
        if test.combination:
            for iter_k, iter_v in test.combination.items():
                self.__insert_in_tree(test, sid_tree["iterators"], [iter_k, iter_v])
            
        if test.state != Test.State.SUCCEED:
            
            self.__insert_in_tree(test, sid_tree["failures"], [])
        return True

    @property
    def session_ids(self):
        return self.rootree.keys()

    def get_tag_cnt(self, sid):
        return len(self.rootree[sid]['tags'].keys())
    
    def get_label_cnt(self, sid):
        return len(self.rootree[sid]["fs-tree"].keys())

    def get_test_cnt(self, sid):
        return sum(self.rootree[sid]['fs-tree']["__metadata"]["count"].values())

    def get_root_path(self, sid):
        return self.rootree[sid]["path"]
    
    def get_sessions(self):
        return [{
                'path': v['path'],
                'state': str(Test.State(v['state'])),
                'sid': k,
                'count': v['fs-tree']['__metadata']['count']
            } for k, v in self.rootree.items()]
