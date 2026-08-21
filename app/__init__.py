import os

from flask import Flask


def create_app(content_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["CONTENT_DIR"] = content_dir or os.environ.get("CONTENT_DIR", "content")

    from . import content, routes

    app.register_blueprint(routes.public)

    @app.context_processor
    def inject_site_config():
        return {"site_config": content.load_site_config(app.config["CONTENT_DIR"])}

    return app
