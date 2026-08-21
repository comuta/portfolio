from flask import Blueprint, current_app, render_template

from . import content

public = Blueprint("public", __name__)


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


@public.route("/")
def index():
    content_dir = _content_dir()
    projects = content.list_projects(content_dir)
    notes = content.list_notes(content_dir)

    latest = sorted(projects + notes, key=lambda p: p.datum, reverse=True)[:3]

    stack = []
    for project in projects:
        for item in project.stack:
            if item not in stack:
                stack.append(item)

    return render_template(
        "index.html",
        latest=latest,
        stack=stack[:6],
    )
