import os
from datetime import timedelta

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from . import bootstrap

# Same reasoning as the web app: TLS is terminated by the host nginx, so no
# force-https redirect here — only the security headers. script-src is 'self'
# (not 'none' like the web app) because the admin UI ships its own JS
# (markdown preview, upload widget) as same-origin static files.
_CSP = {
    "default-src": "'self'",
    "script-src": "'self'",
    "object-src": "'none'",
    "base-uri": "'none'",
    "frame-ancestors": "'none'",
}

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


def create_app(content_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    debug = os.environ.get("FLASK_DEBUG") == "1"

    app.config["CONTENT_DIR"] = content_dir or os.environ.get("CONTENT_DIR", "content")
    app.config["SECRET_KEY"] = _load_secret_key(debug)
    app.config["SESSION_COOKIE_NAME"] = "__Host-session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["SESSION_COOKIE_SECURE"] = not debug
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Talisman(
        app,
        force_https=False,
        strict_transport_security=True,
        content_security_policy=_CSP,
        frame_options="DENY",
        referrer_policy="same-origin",
    )
    csrf.init_app(app)
    limiter.init_app(app)

    @app.after_request
    def add_noindex_header(response):
        # FA-22: admin must never be indexed, even if it leaked into a crawler.
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.route("/robots.txt")
    def robots():
        return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}

    bootstrap.ensure_content_dir(
        app.config["CONTENT_DIR"],
        seed_from=os.environ.get("SEED_CONTENT_DIR"),
    )

    from . import auth, cli

    app.register_blueprint(auth.bp)
    cli.register(app)

    return app


def _load_secret_key(debug: bool) -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if debug:
        return "dev-only-insecure-key-change-me"
    raise RuntimeError("SECRET_KEY environment variable is required outside debug mode")
