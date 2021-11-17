import random

from pcvs.backend.session import Session
from pcvs.testing.test import Test


class DataRepresentation:
    """
    Data Manager from the Flask server side.

    This class manages insertion & requests to the data tree gathering test
    results from a single report server.

    the data representation looks like:

    ```yaml
      0:
    fs-tree:
        <LABEL1>:
            __metadata: {<counts>}
            __elems:
                <subtree1>:
                    __metadata: {<counts>}
                    __elems:
                        <te1>:
                            _metadata: {<counts>}
                            _elems: [Test(), Test(), Test()]
    tags:
        <tag1>:
            __metadata: {<counts>}
            __elems: [Test(), Test(), Test()]
    iter:
        <it_name>:
            __metadata: {<counts>}
            __elems:
                 <possible_value>:
                     __metadata: {<counts>}
                     __elems: [Test(), Test(), Test()]
    failures: [ Test(), Test(), Test()]
    # ...
    ```

    """

    def __init__(self):
        """constructor method"""
        self.rootree = {}

    def __insert_in_tree(self, test, node, depth):
        """insert the given test to the given subtree.

        This function can be called recursively. depth being the list of node
        names where the Test() should be inserted. The 'node' maps to the
        current node level.

        :param test: the test to insert
        :type test: class:`Test`
        :param node: a global tree intermediate node
        :type node: dict
        :param depth: list of node names to walk through
        :type depth: list
        """
        assert('__metadata' in node.keys())

        node["__metadata"]["count"][str(test.state)] += 1

        # if targeted node is reached, insert the test
        if len(depth) == 0:
            if '__elems' not in node:
                node['__elems'] = list()
            node['__elems'].append(test)
        else:
            # create default for the first access + init counters to zero
            node.setdefault('__elems', {})
            node["__elems"].setdefault(depth[0],
                                       {
                "__metadata": {
                    "count": {k: 0 for k in list(map(str, Test.State))}
                }
            })
            self.__insert_in_tree(test, node["__elems"][depth[0]], depth[1:])

    def insert_session(self, sid, session_data):
        """Insert a new session into the tree.

        :param sid: the session id, will be the data key
        :type sid: int
        :param session_data: session basic infos (buildpath, state)
        :type session_data: dict
        """

        # if the SID already exist, a dummy one is generated.
        # a negative value is used to identify such pattern
        if sid in self.rootree.keys():
            while sid in self.rootree.keys():
                sid = random.randint(0, 10000) * (-1)

        # initialize the subtree for this session
        self.rootree.setdefault(sid, {
            "fs-tree": {
                "__metadata": {
                    "count": {k: 0 for k in list(map(str, Test.State))}
                }
            },
            "tags": {
                "__metadata": {
                    "count": {k: 0 for k in list(map(str, Test.State))}
                }
            },
            "iterators": {
                "__metadata": {
                    "count": {k: 0 for k in list(map(str, Test.State))}
                }
            },
            "failures": {
                "__metadata": {
                    "count": {k: 0 for k in list(map(str, Test.State))}
                }
            },
            "state": Session.State(session_data["state"]),
            "path": session_data["buildpath"]
        })

    def close_session(self, sid, session_data):
        """Update the tree when the targeted session is completed.

        :param sid: targeted session id
        :type sid: int
        :param session_data: session infos (state)
        :type session_data: dict
        """
        assert(sid in self.rootree.keys())
        self.rootree[sid]["state"] = session_data["state"]

    def insert_test(self, sid, test: Test):
        """Insert a new test.

        This test is bound to a session.

        :param sid: session id
        :type sid: int
        :param test: test to insert
        :type test: class:`Test`
        :return: a boolean, True if test has been successfully inserted
        :rtype: bool
        """
        # first, insert the test in the hierachy
        label = test.label
        subtree = test.subtree
        te_name = test.te_name

        sid_tree = self.rootree[sid]
        # insert under hierarchical subtree
        self.__insert_in_tree(
            test, sid_tree["fs-tree"], [label, subtree, te_name])

        for tag in test.tags:
            # insert for each tag subtree
            self.__insert_in_tree(test, sid_tree["tags"], [tag])

        if test.combination:
            # insert fo each combination subtree
            for iter_k, iter_v in test.combination.items():
                self.__insert_in_tree(
                    test, sid_tree["iterators"], [iter_k, iter_v])

        if test.state != Test.State.SUCCESS:
            # if failed, save it
            self.__insert_in_tree(test, sid_tree["failures"], [])
        return True

    @property
    def session_ids(self):
        """Get list of registered session ids.

        :return: the list of know session ids
        :rtype: list
        """
        return list(self.rootree.keys())

    def get_tag_cnt(self, sid):
        """Get the number of tag for a given session.

        :param sid: session id
        :type sid: int
        :return: number of tags
        :rtype: int
        """
        return len(self.rootree[sid]['tags'].keys())

    def get_label_cnt(self, sid):
        """Get the number of labels for a given session.

        :param sid: session id
        :type sid: int
        :return: number of labels
        :rtype: int
        """
        return len(self.rootree[sid]["fs-tree"].keys())

    def get_test_cnt(self, sid):
        """Get the numbe rof tests for a given session.

        :param sid: session id
        :type sid: int
        :return: number of tests
        :rtype: int
        """
        return sum(self.rootree[sid]['fs-tree']["__metadata"]["count"].values())

    def get_root_path(self, sid):
        """For a session, get the build path where data are stored.

        :param sid: session id
        :type sid: int
        :return: build path
        :rtype: str
        """
        return self.rootree[sid]["path"]

    def get_token_content(self, sid, token):
        """Advanced function to access partial data tree.

        :param sid: session id
        :type sid: int
        :param token: subtree name to access to
        :type token: str
        :return: the whole data tree segment, empty dict if not found
        :rtype: dict
        """
        if token not in self.rootree[sid]:
            return {}

        return self.rootree[sid][token]

    def extract_tests_under(self, node):
        """Retrieve all tests undef a given data tree subnode.

        :param node: data subnode
        :type node: dict
        :return: list of tests under this subnode
        :rtype: list(class:`Test`)
        """
        assert('__elems' in node.keys())
        if isinstance(node['__elems'], list):
            return [x.to_json(strstate=True) for x in node['__elems'] if isinstance(x, Test)]

        ret = list()
        for elt in node['__elems'].values():
            ret += self.extract_tests_under(elt)
        return ret

    def get_sessions(self):
        """Get the list of current known sessions.

        :return: a dict mapping to session infos.
        :rtype: list of dicts
        """
        return [{
                'path': v['path'],
                'state': str(Session.State(v['state'])),
                'sid': k,
                'count': v['fs-tree']['__metadata']['count']
                } for k, v in self.rootree.items()]
