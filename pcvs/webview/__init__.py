import os
import copy
import random
            
from flask import Flask, abort, jsonify, render_template, request, sessions
from pcvs.testing.test import Test
import json

from pcvs import PATH_INSTDIR
from pcvs.testing.test import Test
from pcvs.backend import session


def create_app(global_tree=None, test_config=None):
    """Start and run the Flask application.

    :param global_tree: the full static result tree.
    :type global_tree: dict
    :param test_config: the loaded run configuration.
    :type test_config: dict
    :return: the application
    :rtype: :class:`Flask`
    """
    global_tree_recv = {}

    app = Flask(__name__, template_folder=os.path.join(
        PATH_INSTDIR, "webview/templates"))

    # app.config.from_object(...)
    @app.route('/about')
    def about():
        """Provide the about-us page.

        :return: webpage content
        :rtype: str
        """
        return render_template('tbw.html')

    @app.route('/doc')
    def doc():
        """Provide the doc page.

        :return: webpage content
        :rtype: str
        """
        return render_template('tbw.html')

    @app.route('/welcome')
    @app.route('/main')
    @app.route('/')
    def root():
        """Provide the main page.

        :return: webpage content
        :rtype: str
        """
        if 'json' in request.args.get("render", []):
            res = list()
            for k in global_tree_recv.keys():
                res.append({
                    "path": global_tree_recv[k]["path"],
                    "state": str(session.Session.State(global_tree_recv[k]["state"])),
                    "count": global_tree_recv[k]["fs-tree"]["__metadata"]["count"],
                    "sid": k
                    })
            return jsonify(res)
        return render_template("main.html")
    
    @app.route("/run/<sid>")
    def session_main(sid):
        sid = int(sid)
        assert(sid in global_tree_recv)
        
        if 'json' in request.args.get('render', []):
            return jsonify({"tag": len(global_tree_recv[sid]["tags"].keys()),
                            "label": len(global_tree_recv[sid]["fs-tree"].keys()),
                            "test": sum(global_tree_recv[sid]["fs-tree"]["__metadata"]["count"].values()),
                            "files": -1})
        return render_template('session_main.html',
                               sid=sid,
                               rootdir=global_tree_recv[sid]["path"],
                               nb_tests=sum(global_tree_recv[sid]["fs-tree"]["__metadata"]["count"].values()),
                               nb_labels=len(global_tree_recv[sid]["fs-tree"].keys()),
                               nb_tags=len(global_tree_recv[sid]["tags"].keys()),
                               nb_files=-1)

    @app.route('/compare')
    def compare():
        """Provide the archive comparaison interface.

        :return: webpage content
        :rtype: str
        """
        return render_template('tbw.html')

    @app.route("/run/<sid>/<selection>/list")
    def get_list(sid, selection):
        """Get a listing.

        The response will depend on the request, which can be:
            * tag
            * label
            * status

        Providing a GET ``render`` to ``json`` returns the raw JSON version.

        :param selection: which listing to target
        :type selection: str
        :return: web content
        :rtype: str
        """
        sid = int(sid)
        if 'json' not in request.args.get('render', []):
            return render_template('list_view.html', sid=sid, selection=selection)

        out = list()
        for name, value in global_tree_recv[sid][selection].items():
            out.append({
                "name": name,
                "count": value['metadata']['count']
            })

    @app.route("/run/<sid>/<selection>/detail")
    def get_details(sid, selection):
        """Get a detailed view of a component.

        The response will depend on the request, which can be:
            * tag
            * label
            * status

        Providing a GET ``render`` to ``json`` returns the raw JSON version.

        :param selection: which view to target
        :type selection: str
        :return: web response
        :rtype: str
        """
        sid = int(sid)
        out = list()
        request_item = request.args.get('name', None)

        if selection not in global_tree.keys():
            abort(404, description="{} is not a valid selection!".format(selection))

        if 'json' not in request.args.get('render', []):
            return render_template("detailed_view.html",
                                   sid=sid,
                                   selection=selection,
                                   sel_item=request_item)

        if request_item in global_tree_recv[sid][selection].keys():
            for test in global_tree_recv[sid][selection][request_item]['tests']:
                out.append(test.to_json())
        return jsonify(out)

    @app.route("/submit/session_init", methods=["POST"])
    def submit_new_session():
        json_session = request.get_json()
        sid = json_session["sid"]
        if sid in global_tree_recv.keys():
            while sid in global_tree_recv.keys():
                sid = random.randint(0, 10000)
            
        global_tree_recv.setdefault(sid, {
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
            "state": session.Session.State(json_session["state"]),
            "path": json_session["buildpath"]
        })
        return "OK!", 200
    
    @app.route("/submit/session_fini", methods=["POST"])
    def submit_end_session():
        json_session = request.get_json()
        assert(json_session["sid"] in global_tree_recv.keys())
        global_tree_recv[json_session["sid"]]["state"] = json_session["state"]
        return "OK!", 200
    
    @app.route("/submit/test", methods=["POST"])
    def submit():
        json_str = request.get_json()
        
        test_sid = json_str["metadata"]["sid"]
        test_obj = Test()
        
        test_obj.from_json(json_str["test_data"])
        
        ok = _insert_to_split(test_sid, test_obj)
        
        if not ok:
            return "", 406
        else:
            return "OK!", 200
    
    def __insert_in_tree(test, node, depth):
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
                __insert_in_tree(test, node["__elems"][depth[0]], depth[1:])
        
    def _insert_to_split(sid, test: Test):
        # first, insert the test in the hierachy
        label = test.label
        subtree = test.subtree
        te_name = test.te_name
        
        sid_tree = global_tree_recv[sid]
        __insert_in_tree(test, sid_tree["fs-tree"], [label, subtree, te_name])
        
        for tag in test.tags:
            __insert_in_tree(test, sid_tree["tags"], [tag])
        
        if test.combination:
            for iter_k, iter_v in test.combination.items():
                __insert_in_tree(test, sid_tree["iterators"], [iter_k, iter_v])
            
        if test.state != Test.State.SUCCEED:
            
            __insert_in_tree(test, sid_tree["failures"], [])
        return True

    @app.errorhandler(404)
    def page_not_found(e):
        """404 Not found page handler.

        :param e: the caught error, only 404 here
        :type e: int
        :return: web content
        :rtype: str
        """
        return render_template('404.html')
    return app
