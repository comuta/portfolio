import os

from flask import Flask


def create_app(content_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["CONTENT_DIR"] = content_dir or os.environ.get("CONTENT_DIR", "content")

    from . import routes

    app.register_blueprint(routes.public)

    return app
