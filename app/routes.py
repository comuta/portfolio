import math

from flask import Blueprint, current_app, render_template, request

from . import content

public = Blueprint("public", __name__)

PROJECTS_PAGE_SIZE = 5


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


def _current_page() -> int:
    try:
        return max(1, int(request.args.get("seite", "1")))
    except ValueError:
        return 1


def _render_project_listing(all_projects, filtered_projects, active_label):
    themen = sorted({t for p in all_projects for t in p.themen})
    stacks = sorted({s for p in all_projects for s in p.stack})

    total_pages = max(1, math.ceil(len(filtered_projects) / PROJECTS_PAGE_SIZE))
    page = min(_current_page(), total_pages)
    start = (page - 1) * PROJECTS_PAGE_SIZE
    page_items = filtered_projects[start:start + PROJECTS_PAGE_SIZE]

    return render_template(
        "projects.html",
        projects=page_items,
        total_count=len(filtered_projects),
        themen=themen,
        stacks=stacks,
        active_label=active_label,
        page=page,
        total_pages=total_pages,
    )


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


@public.route("/projekte")
def projects():
    all_projects = content.list_projects(_content_dir())
    return _render_project_listing(all_projects, all_projects, "alle")


@public.route("/projekte/thema/<thema>")
def projects_by_thema(thema):
    all_projects = content.list_projects(_content_dir())
    filtered = [p for p in all_projects if thema in p.themen]
    return _render_project_listing(all_projects, filtered, f"thema:{thema}")


@public.route("/projekte/stack/<stack_name>")
def projects_by_stack(stack_name):
    all_projects = content.list_projects(_content_dir())
    filtered = [p for p in all_projects if stack_name in p.stack]
    return _render_project_listing(all_projects, filtered, f"stack:{stack_name}")
