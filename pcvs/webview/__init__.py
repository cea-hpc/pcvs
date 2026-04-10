import os

from flask import abort
from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
from flask import Response

from pcvs import PATH_INSTDIR
from pcvs.backend.report import Report
from pcvs.testing.test import Test

DATA_MANAGER = None


def create_app(report: Report) -> Flask:
    """Start and run the Flask application.

    :param report: The report manager that contain tests info for the flask app.
    :return: the application
    """
    global DATA_MANAGER
    DATA_MANAGER = report

    app = Flask(__name__, template_folder=os.path.join(PATH_INSTDIR, "webview/templates"))

    def sanitize_sid(sid: str) -> str:
        if sid not in DATA_MANAGER.session_ids:
            abort(404)
        else:
            return sid

    def sanitize_selection(selection: str) -> str:
        if selection not in ["tags", "labels", "status"]:
            abort(404)
        else:
            return selection

    # app.config.from_object(...)
    @app.route("/about")
    def about() -> Response:
        """Provide the about-us page.

        :return: webpage content
        """
        return Response(render_template("tbw.html"))

    @app.route("/doc")
    def doc() -> Response:
        """Provide the doc page.

        :return: webpage content
        """
        return Response(render_template("tbw.html"))

    @app.route("/welcome")
    @app.route("/main")
    @app.route("/")
    def root() -> Response:
        """Provide the main page.

        :return: webpage content
        """
        if "json" in request.args.get("render", []):
            return jsonify(list(DATA_MANAGER.session_infos()))
        return Response(render_template("main.html"))

    @app.route("/run/<sid>")
    def session_main(sid: str) -> Response:
        """Provide the per-session main page

        :param sid: session id
        :return: page content
        """
        sid = sanitize_sid(sid)

        labels = DATA_MANAGER.single_session_labels(sid)
        tags = DATA_MANAGER.single_session_tags(sid)
        jobs_cnt = DATA_MANAGER.single_session_job_cnt(sid)

        if "json" in request.args.get("render", []):
            return jsonify(
                {
                    "tag": len(tags),
                    "label": len(labels),
                    "test": jobs_cnt,
                    "config": DATA_MANAGER.single_session_config(sid),
                }
            )
        return Response(
            render_template(
                "session_main.html",
                sid=sid,
                rootdir=DATA_MANAGER.single_session_build_path(sid),
                nb_tests=jobs_cnt,
                nb_labels=len(labels),
                nb_tags=len(tags),
            )
        )

    @app.route("/compare")
    def compare() -> Response:
        """Provide the archive comparison interface.

        :return: webpage content
        """
        return Response(render_template("tbw.html"))

    @app.route("/run/<sid>/<selection>/list")
    def get_list(sid: str, selection: str) -> Response:
        """Get a listing.

        The response will depend on the request, which can be:
            * tags
            * labels
            * status

        Providing a GET ``render`` to ``json`` returns the raw JSON version.

        :param sid: The session id.
        :param selection: which listing to target
        :return: web content
        """
        sid = sanitize_sid(sid)
        selection = sanitize_selection(selection)

        if "json" in request.args.get("render", []):
            out = []
            infos = DATA_MANAGER.single_session_get_view(sid, selection, summary=True)
            assert infos is not None
            for k, v in infos.items():
                out.append({"name": k, "count": v})
            return jsonify(out)

        return Response(render_template("list_view.html", sid=sid, selection=selection))

    @app.route("/run/<sid>/<selection>/detail")
    def get_details(sid: str, selection: str) -> Response:
        """Get a detailed view of a component.

        The response will depend on the request, which can be:
            * tag
            * label
            * status

        Providing a GET ``render`` to ``json`` returns the raw JSON version.

        :param sid: The session id.
        :param selection: which view to target
        :return: web response
        """
        sid = sanitize_sid(sid)
        selection = sanitize_selection(selection)
        unsafe_request_item = request.args.get("name", None)

        out = []
        if "json" in request.args.get("render", []):
            # special case
            if selection == "status":
                job_list = DATA_MANAGER.single_session_status(
                    sid, unsafe_status_filter=unsafe_request_item
                )
            else:
                struct = DATA_MANAGER.single_session_get_view(
                    sid, selection, unsafe_subset=unsafe_request_item, summary=False
                )
                # jobs are returned split into 3 lists, depending on their status
                # -> browse all three lists
                if struct is None:
                    return Response("Not Found !", 404)
                job_list = []
                for _, m in struct.items():
                    for _, s in m.items():
                        job_list += s
            for elt in job_list:
                cur: Test | None = DATA_MANAGER.single_session_map_id(sid, elt)
                if cur is not None:
                    out.append(cur.to_json(strstate=True))

            return jsonify(out)

        return Response(
            render_template(
                "detailed_view.html", sid=sid, selection=selection, sel_item=unsafe_request_item
            ),
            200,
        )

    @app.errorhandler(404)
    def page_not_found(e: int) -> Response:  # pylint: disable=unused-argument
        """
        404 Not found page handler.

        :param e: the caught error, only 404 here
        :return: web content
        """
        return Response(render_template("404.html"))

    return app


def start_server(report: Report) -> int:
    """Initialize the Flask server, default to 5000.

    A random port is picked if the default is already in use.
    :param report: The model to be used.
    :return: 0 (app.run does not send a return code).
    """
    app = create_app(report)
    app.run(host="0.0.0.0", port=int(os.getenv("PCVS_REPORT_PORT", str(5000))), debug=True)
    return 0
