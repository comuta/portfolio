from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request
from pydantic import ValidationError

from shared import content

from . import media
from . import posts_repo as repo
from . import storage, versioning
from .auth import login_required

bp = Blueprint("posts", __name__)


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


@bp.route("/")
@login_required
def dashboard():
    entries = repo.iter_all_posts(_content_dir())
    return render_template("dashboard.html", entries=entries)


@bp.route("/beitraege/neu", methods=["GET", "POST"])
@login_required
def new_post():
    if request.method == "POST":
        return _save_post(dir_name=None, path=None, visibility="privat")
    return render_template("post_form.html", values={}, inhalt="", dir_name=None, visibility=None)


@bp.route("/beitraege/<dir_name>/bearbeiten", methods=["GET", "POST"])
@login_required
def edit_post(dir_name):
    found = repo.find_post_dir(_content_dir(), dir_name)
    if found is None:
        abort(404)
    path, visibility = found

    if request.method == "POST":
        return _save_post(dir_name=dir_name, path=path, visibility=visibility)

    entry = repo.load_entry(path, visibility)
    if entry.post is None:
        flash(f"meta.json ist fehlerhaft: {entry.error}", "error")
        return render_template("post_form.html", values={}, inhalt=repo.read_inhalt(path), dir_name=dir_name, visibility=visibility)

    values = repo.post_to_form_values(entry.post)
    return render_template("post_form.html", values=values, inhalt=repo.read_inhalt(path), dir_name=dir_name, visibility=visibility)


def _save_post(dir_name: str | None, path: Path | None, visibility: str):
    content_dir = _content_dir()
    try:
        data = repo.parse_form(request.form)
        post = content.Post.model_validate(data)
    except ValidationError as exc:
        flash(f"Ungültige Eingabe: {exc}", "error")
        return render_template("post_form.html", values=request.form, inhalt=request.form.get("inhalt", ""), dir_name=dir_name, visibility=visibility), 400

    is_new = path is None
    if is_new:
        dir_name = repo.make_dir_name(content_dir, post.datum, post.titel)
        path = Path(content_dir) / "beitraege" / visibility / dir_name

    meta = post.model_dump(mode="json", exclude={"slug", "dir_name", "content_html"})
    storage.atomic_write_json(path / "meta.json", meta)
    storage.atomic_write_text(path / "inhalt.md", request.form.get("inhalt", ""))

    action = "angelegt" if is_new else "bearbeitet"
    versioning.commit_all(Path(content_dir), f"Beitrag {action}: {dir_name}")
    flash("Beitrag gespeichert.", "success")
    return redirect(f"/beitraege/{dir_name}/bearbeiten")


@bp.route("/beitraege/<dir_name>/veroeffentlichen", methods=["POST"])
@login_required
def publish(dir_name):
    _move_visibility(dir_name, "oeffentlich")
    flash("Beitrag veröffentlicht.", "success")
    return redirect("/")


@bp.route("/beitraege/<dir_name>/zurueckziehen", methods=["POST"])
@login_required
def unpublish(dir_name):
    _move_visibility(dir_name, "privat")
    flash("Beitrag zurückgezogen.", "success")
    return redirect("/")


def _move_visibility(dir_name: str, to: str) -> None:
    content_dir = _content_dir()
    found = repo.find_post_dir(content_dir, dir_name)
    if found is None:
        abort(404)
    path, current_visibility = found
    if current_visibility == to:
        return
    target = Path(content_dir) / "beitraege" / to / dir_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))
    versioning.commit_all(Path(content_dir), f"Beitrag {'veröffentlicht' if to == 'oeffentlich' else 'zurückgezogen'}: {dir_name}")


@bp.route("/beitraege/<dir_name>/loeschen", methods=["POST"])
@login_required
def delete_post(dir_name):
    content_dir = _content_dir()
    found = repo.find_post_dir(content_dir, dir_name)
    if found is None:
        abort(404)
    path, visibility = found

    trash_root = Path(content_dir) / ".papierkorb"
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    target = trash_root / f"{stamp}__{visibility}__{dir_name}"
    shutil.move(str(path), str(target))

    versioning.commit_all(Path(content_dir), f"Beitrag in Papierkorb verschoben: {dir_name}")
    flash("Beitrag in den Papierkorb verschoben.", "success")
    return redirect("/")


@bp.route("/beitraege/<dir_name>/medien/hochladen", methods=["POST"])
@login_required
def upload_media(dir_name):
    content_dir = _content_dir()
    found = repo.find_post_dir(content_dir, dir_name)
    if found is None:
        abort(404)
    path, _visibility = found

    file_storage = request.files.get("datei")
    if file_storage is None:
        return {"error": "Keine Datei übermittelt."}, 400

    try:
        filename = media.save_validated_image(file_storage, path / "medien")
    except media.UploadError as exc:
        return {"error": str(exc)}, 400

    versioning.commit_all(Path(content_dir), f"Medium hochgeladen: {dir_name}/medien/{filename}")
    return {"pfad": f"medien/{filename}"}


@bp.route("/vorschau", methods=["POST"])
@login_required
def preview():
    text = request.form.get("inhalt", "")
    return content.render_markdown(text)
