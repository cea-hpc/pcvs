from flask import Flask, abort, jsonify, render_template, request
import os
from pcvs import PATH_INSTDIR

def create_app(global_tree=None, test_config=None):
    app = Flask(__name__, template_folder=os.path.join(PATH_INSTDIR, "webview/templates"))

    #app.config.from_object(...)
    @app.route('/about')
    def about():
        return render_template('tbw.html')

    @app.route('/doc')
    def doc():
        return render_template('tbw.html')

    @app.route('/welcome')
    @app.route('/main')
    @app.route('/')
    def root():
        return render_template('main.html',
            rootdir=global_tree['metadata']['rootdir'],
            nb_tests=global_tree['metadata']['count']['tests'],
            nb_labels=global_tree['metadata']['count']['labels'],
            nb_tags=global_tree['metadata']['count']['tags'],
            nb_files=global_tree['metadata']['count']['files'])
    
    @app.route('/realtime')
    def rt():
        return render_template('tbw.html')

    @app.route('/compare')
    def compare():
        return render_template('tbw.html')

    @app.route("/stats")
    @app.route("/statistics")
    @app.route('/summary')
    def stats():
        return render_template('tbw.html')

    @app.route("/<selection>/list")
    def get_list(selection):
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
        return render_template('404.html')
    return app