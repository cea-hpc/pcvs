import os
import copy
import random
            
from flask import Flask, abort, jsonify, render_template, request, sessions
from pcvs.testing.test import Test
import json

from pcvs import PATH_INSTDIR
from pcvs.testing.test import Test
from pcvs.backend import session
from pcvs.webview import datalayer

data_manager = datalayer.DataRepresentation()

def create_app():
    """Start and run the Flask application.

    :return: the application
    :rtype: :class:`Flask`
    """
    global data_manager

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
            return jsonify(data_manager.get_sessions())
        return render_template("main.html")
    
    @app.route("/run/<sid>")
    def session_main(sid):
        sid = int(sid)
        assert(sid in data_manager.session_ids)
        
        if 'json' in request.args.get('render', []):
            return jsonify({"tag": data_manager.get_tag_cnt(sid),
                            "label": data_manager.get_label_cnt(sid),
                            "test": data_manager.get_test_cnt(sid),
                            "files": -1})
        return render_template('session_main.html',
                               sid=sid,
                               rootdir=data_manager.get_root_path(sid),
                               nb_tests=data_manager.get_test_cnt(sid),
                               nb_labels=data_manager.get_label_cnt(sid),
                               nb_tags=data_manager.get_tag_cnt(sid),
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
        data_manager.insert_session(sid, json_session)

        return "OK!", 200
    
    @app.route("/submit/session_fini", methods=["POST"])
    def submit_end_session():
        json_session = request.get_json()
        data_manager.close_session(json_session["sid"], json_session)
        return "OK!", 200
 
    @app.route("/submit/test", methods=["POST"])
    def submit():
        json_str = request.get_json()
        
        test_sid = json_str["metadata"]["sid"]
        test_obj = Test()
        
        test_obj.from_json(json_str["test_data"])
        
        ok = data_manager.insert_test(test_sid, test_obj)
        
        if not ok:
            return "", 406
        else:
            return "OK!", 200
    

    @app.errorhandler(404)
    def page_not_found(e):
        """404 Not found page handler.

        :param e: the caught error, only 404 here
        :type e: int
        :return: web content
        :rtype: str
        """
        return render_template('404.html')

    def get_data_manager():
        return data_manager

    return app
