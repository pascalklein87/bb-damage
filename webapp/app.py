import os
import pathlib
import time

from flask import Flask, redirect, request, render_template, send_from_directory


# Sibling bb-engine repo's browser JS (its nimbleMultiplier is the ONE JavaScript
# home for the Nimble formula), served at /bb-engine/<path> so the damage
# calculator reuses it instead of a copied formula. Located depth-robustly:
# bb-engine sits beside this workspace (bloodngold-projects/ locally, /var/www/
# on the box).
def _bb_engine_js_dir():
    for anc in pathlib.Path(__file__).resolve().parents:
        if (anc / "bb-engine" / "js").is_dir():
            return anc / "bb-engine" / "js"
    raise RuntimeError("bb-engine/js sibling not found above " + __file__)


_BB_ENGINE_JS = _bb_engine_js_dir()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

    @app.context_processor
    def inject_cache_bust():
        return {'cache_bust': int(time.time())}

    @app.context_processor
    def inject_tabs_js_url():
        # Cross-site vertical tab bar, hosted once at bloodngold.com/static/tabs.js.
        # Local dev overrides TABS_JS_URL to the local bng-home dev server.
        return {'tabs_js_url': os.environ.get(
            'TABS_JS_URL', 'https://bloodngold.com/static/tabs.js')}

    # Calculator at / and the cache view at /cache (tools_bp has no url_prefix).
    from tools.routes import tools_bp
    app.register_blueprint(tools_bp)

    @app.route('/bb-engine/<path:path>')
    def bb_engine_js(path):
        """Serve bb-engine's browser JS (attack.js) from the sibling repo so the
        damage calculator reuses bb-engine's ONE nimbleMultiplier."""
        return send_from_directory(_BB_ENGINE_JS, path)

    @app.route('/spec')
    def spec():
        return render_template('damage_spec.html')

    @app.route('/robots.txt')
    def robots_txt():
        return send_from_directory(app.static_folder, 'robots.txt')

    @app.route('/sitemap.xml')
    def sitemap_xml():
        return send_from_directory(app.static_folder, 'sitemap.xml',
                                   mimetype='application/xml')

    # Legacy paths from when the calculator lived at bloodngold.com/damage-calculator.
    @app.route('/damage-calculator', strict_slashes=False)
    def legacy_calculator():
        qs = request.query_string.decode()
        return redirect('/?' + qs if qs else '/', code=301)

    @app.route('/damage-calculator/cache')
    def legacy_cache():
        return redirect('/cache', code=301)

    @app.route('/calculator', strict_slashes=False)
    def legacy_calculator_short():
        qs = request.query_string.decode()
        return redirect('/?' + qs if qs else '/', code=301)

    @app.errorhandler(404)
    def not_found(e):
        return redirect('/', code=302)

    return app


if __name__ == '__main__':
    app = create_app()
    # Local dev port. 5005 (not 5002) so it never collides with bng-game,
    # which runs on 5002. Prod is unaffected: gunicorn serves create_app()
    # on 8002 (see deploy.sh), never this app.run().
    app.run(debug=True, port=5005)
