import math
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from shared import content

public = Blueprint("public", __name__)

PROJECTS_PAGE_SIZE = 5
FEED_DEFAULT_LIMIT = 20
FEED_MAX_LIMIT = 100
PORTRAIT_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif", "svg")


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


def _find_portrait_ext() -> str | None:
    seiten = Path(_content_dir()) / "seiten"
    for ext in PORTRAIT_EXTENSIONS:
        if (seiten / f"portrait.{ext}").is_file():
            return ext
    return None


def _current_page() -> int:
    try:
        return max(1, int(request.args.get("seite", "1")))
    except ValueError:
        return 1


def _render_project_listing(all_projects, filtered_projects, active_stack, active_thema):
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
        active_stack=active_stack,
        active_thema=active_thema,
        page=page,
        total_pages=total_pages,
    )


@public.route("/healthz")
def healthz():
    # For Docker's HEALTHCHECK/monitoring — cheap on purpose, just a stat()
    # to catch a totally missing/unmounted content dir.
    if not Path(_content_dir()).is_dir():
        return "content dir missing", 503
    return "ok", 200


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
    active_stack = request.args.get("stack") or None
    active_thema = request.args.get("thema") or None

    filtered = all_projects
    if active_stack:
        filtered = [p for p in filtered if active_stack in p.stack]
    if active_thema:
        filtered = [p for p in filtered if active_thema in p.themen]

    return _render_project_listing(all_projects, filtered, active_stack, active_thema)


# Alte pfadbasierte Filter-URLs (vor den Dropdown-Filtern) — als Redirect
# erhalten, falls irgendwo verlinkt oder ein Suchmaschinen-Crawler den
# alten Pfad noch kennt.
@public.route("/projekte/thema/<thema>")
def projects_by_thema(thema):
    return redirect(url_for("public.projects", thema=thema))


@public.route("/projekte/stack/<stack_name>")
def projects_by_stack(stack_name):
    return redirect(url_for("public.projects", stack=stack_name))


def _get_post_or_404(slug: str) -> content.Post:
    post = content.get_post(_content_dir(), slug)
    if post is None:
        abort(404)
    return post


@public.route("/projekte/<slug>/")
def project_detail(slug):
    post = _get_post_or_404(slug)
    if post.typ != "projekt":
        abort(404)

    projects = content.list_projects(_content_dir())
    next_post = None
    for i, p in enumerate(projects):
        if p.slug == slug and i + 1 < len(projects):
            next_post = projects[i + 1]
            break

    return render_template("project_detail.html", post=post, next_post=next_post)


@public.route("/notizen")
def notes():
    return render_template("notes.html", notes=content.list_notes(_content_dir()))


@public.route("/ueber-mich")
def about():
    body_html = content.load_page(_content_dir(), "ueber-mich")
    return render_template("about.html", body_html=body_html, portrait_ext=_find_portrait_ext())


@public.route("/impressum")
def imprint():
    # The structured impressum fields in site.config.json (edited under
    # /einstellungen, gated behind an explicit confirmation — FA-23) are the
    # actual legally-required content; seiten/impressum.md is free-text
    # supplementary material only (e.g. a note on content responsibility
    # phrasing), not a replacement for it.
    body_html = content.load_page(_content_dir(), "impressum")
    return render_template("impressum.html", body_html=body_html)


@public.route("/datenschutz")
def privacy():
    body_html = content.load_page(_content_dir(), "datenschutz")
    return render_template("legal_page.html", title="Datenschutzerklärung", body_html=body_html)


@public.route("/ueber-mich/portrait.<ext>")
def about_portrait(ext):
    if ext not in PORTRAIT_EXTENSIONS:
        abort(404)

    seiten = (Path(_content_dir()) / "seiten").resolve()
    ziel = (seiten / f"portrait.{ext}").resolve()
    if not ziel.is_relative_to(seiten) or not ziel.is_file():
        abort(404)

    return send_from_directory(seiten, f"portrait.{ext}")


@public.route("/projekte/<slug>/medien/<path:dateiname>")
def project_medium(slug, dateiname):
    post = _get_post_or_404(slug)

    medien_dir = (Path(_content_dir()) / "beitraege" / "oeffentlich" / post.dir_name / "medien").resolve()
    ziel = (medien_dir / dateiname).resolve()
    if not ziel.is_relative_to(medien_dir) or not ziel.is_file():
        abort(404)

    return send_from_directory(medien_dir, dateiname)


@public.route("/feed.xml")
def feed():
    # Notizen was previously missing entirely, despite /notizen linking here
    # as "its" feed — both belong, sorted together chronologically like the
    # Startseite's "letzte einträge" table.
    entries = sorted(
        content.list_projects(_content_dir()) + content.list_notes(_content_dir()),
        key=lambda item: item.datum,
        reverse=True,
    )

    try:
        limit = int(request.args.get("limit", FEED_DEFAULT_LIMIT))
    except ValueError:
        limit = FEED_DEFAULT_LIMIT
    limit = max(1, min(limit, FEED_MAX_LIMIT))

    xml = render_template("feed.xml", entries=entries[:limit])
    return Response(xml, mimetype="application/atom+xml")


@public.app_errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        title="Diese Seite gibt es nicht.",
        message=(
            "Der angeforderte Beitrag existiert nicht oder ist nicht öffentlich. "
            "Ein unbekannter Slug wird nie in einen Dateipfad eingesetzt."
        ),
    ), 404


@public.app_errorhandler(500)
def server_error(error):
    current_app.logger.exception("internal server error")
    return render_template(
        "error.html",
        code=500,
        title="Etwas ist schiefgelaufen.",
        message="Der Fehler wurde protokolliert. Bitte versuchen Sie es später erneut.",
    ), 500
