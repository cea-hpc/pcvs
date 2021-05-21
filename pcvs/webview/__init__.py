import os

from flask import Flask, abort, jsonify, render_template, request

from pcvs import PATH_INSTDIR


def create_app(global_tree=None, test_config=None):
    """Start and run the Flask application.

    :param global_tree: the full static result tree.
    :type global_tree: dict
    :param test_config: the loaded run configuration.
    :type test_config: dict
    :return: the application
    :rtype: :class:`Flask`
    """
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
        return render_template('main.html',
                               rootdir=global_tree['metadata']['rootdir'],
                               nb_tests=global_tree['metadata']['count']['tests'],
                               nb_labels=global_tree['metadata']['count']['labels'],
                               nb_tags=global_tree['metadata']['count']['tags'],
                               nb_files=global_tree['metadata']['count']['files'])

    @app.route('/realtime')
    def rt():
        """Access to the realtime interface.

        :return: webpage content
        :rtype: str
        """
        return render_template('tbw.html')

    @app.route('/compare')
    def compare():
        """Provide the archive comparaison interface.

        :return: webpage content
        :rtype: str
        """
        return render_template('tbw.html')

    @app.route("/<selection>/list")
    def get_list(selection):
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
        if 'json' not in request.args.get('render', []):
            return render_template('list_view.html', selection=selection)

        out = list()
        for name, value in global_tree[selection].items():
            out.append({
                "name": name,
                "count": value['metadata']['count']
            })
        return jsonify(out)

    @app.route("/<selection>/detail")
    def get_details(selection):
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
        out = list()
        request_item = request.args.get('name', None)

        if selection not in global_tree.keys():
            abort(404, description="{} is not a valid selection!".format(selection))

        if 'json' not in request.args.get('render', []):
            return render_template("detailed_view.html",
                                   selection=selection,
                                   sel_item=request_item)

        if request_item in global_tree[selection].keys():
            for test in global_tree[selection][request_item]['tests']:
                out.append(test)
        return jsonify(out)

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
