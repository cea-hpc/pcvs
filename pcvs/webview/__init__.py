import copy
import json
import os
import random

from flask import Flask, abort, jsonify, render_template, request, sessions

from pcvs import PATH_INSTDIR
from pcvs.testing.test import Test

data_manager = None


def create_app(iface):
    """Start and run the Flask application.

    :return: the application
    :rtype: :class:`Flask`
    """
    global data_manager
    data_manager = iface

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
            return jsonify(list(data_manager.session_infos()))
        return render_template("main.html")

    @app.route("/run/<sid>")
    def session_main(sid):
        """Provide the per-session main page

        :param sid: session id
        :type sid: str
        :return: page content
        :rtype: str
        """
        sid = int(sid)
        if sid not in data_manager.session_ids:
            abort(404)

        labels = data_manager.single_session_labels(sid)
        tags = data_manager.single_session_tags(sid)
        jobs_cnt = data_manager.single_session_job_cnt(sid)

        if 'json' in request.args.get('render', []):
            return jsonify({"tag": len(tags),
                            "label": len(labels),
                            "test": jobs_cnt,
                            "config": data_manager.single_session_config(sid)
                            })
        return render_template('session_main.html',
                               sid=sid,
                               rootdir=data_manager.single_session_build_path(
                                   sid),
                               nb_tests=jobs_cnt,
                               nb_labels=len(labels),
                               nb_tags=len(tags)
                               )

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
            * tags
            * label
            * status

        Providing a GET ``render`` to ``json`` returns the raw JSON version.

        :param selection: which listing to target
        :type selection: str
        :return: web content
        :rtype: str
        """
        sid = int(sid)
        if 'json' in request.args.get('render', []):
            out = list()
            infos = data_manager.single_session_get_view(
                sid, selection, summary=True)
            for k, v in infos.items():
                out.append({
                    "name": k,
                    "count": v
                })
            return jsonify(out)

        return render_template('list_view.html', sid=sid, selection=selection)

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

        if 'json' in request.args.get('render', []):
            # special case
            if selection == "status":
                job_list = data_manager.single_session_status(
                    sid, filter=request_item)
            else:
                struct = data_manager.single_session_get_view(
                    sid, selection, subset=request_item, summary=False)
                # jobs are returned split into 3 lists, depending on their status
                # -> browse all three lists
                job_list = list()
                for e, m in struct.items():
                    for sn, s in m.items():
                        job_list += s
            for elt in job_list:
                cur: Test = data_manager.single_session_map_id(sid, elt)
                out.append(cur.to_json(strstate=True))

            return jsonify(out)

        return render_template("detailed_view.html",
                               sid=sid,
                               selection=selection,
                               sel_item=request_item)

    @app.route("/submit/session_init", methods=["POST"])
    def submit_new_session():
        """Entry point to receive new session request.

        :return: OK
        :rtype: HTTP request
        """
        json_session = request.get_json()
        sid = json_session["sid"]
        data_manager.add_session(sid, json_session)

        return "OK!", 200

    @app.route("/submit/session_fini", methods=["POST"])
    def submit_end_session():
        """Entry point to request a session end.

        :return: OK
        :rtype: HTTP request
        """
        return "OK!", 200

    @app.route("/submit/test", methods=["POST"])
    def submit():
        """Entry point to receive test data.

        :return: OK
        :rtype: HTTP request
        """
        return "OK!", 200
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

    return app
