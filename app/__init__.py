import os

from flask import Flask
from flask_talisman import Talisman

# TLS itself is terminated by the host nginx in front of this app (AE-01), so
# we don't force an HTTPS redirect here — only send the security headers.
_CSP = {
    "default-src": "'self'",
    "script-src": "'none'",
    "object-src": "'none'",
    "base-uri": "'none'",
}


def create_app(content_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["CONTENT_DIR"] = content_dir or os.environ.get("CONTENT_DIR", "content")

    Talisman(
        app,
        force_https=False,
        strict_transport_security=True,
        content_security_policy=_CSP,
        frame_options="DENY",
        referrer_policy="same-origin",
    )

    from . import content, routes

    app.register_blueprint(routes.public)

    @app.context_processor
    def inject_site_config():
        return {"site_config": content.load_site_config(app.config["CONTENT_DIR"])}

    return app
