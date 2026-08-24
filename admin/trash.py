"""List/restore/permanently-delete .papierkorb/ entries (FA-23: "Löschen
verschiebt nach .papierkorb/, Leeren erfolgt manuell").

Entries are named <timestamp>__<visibility>__<dir_name> by posts.py's
delete_post(), which is enough to restore a post to exactly where it was.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template

from . import versioning
from .auth import login_required

bp = Blueprint("trash", __name__)


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


def _trash_root(content_dir: str) -> Path:
    return Path(content_dir) / ".papierkorb"


def _parse_entry_name(name: str) -> tuple[str, str, str] | None:
    parts = name.split("__", 2)
    if len(parts) != 3:
        return None
    stamp, visibility, dir_name = parts
    if visibility not in ("oeffentlich", "privat"):
        return None
    return stamp, visibility, dir_name


def _format_stamp(stamp: str) -> str:
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stamp


def _resolve_trash_entry(content_dir: str, raw_name: str) -> Path | None:
    root = _trash_root(content_dir).resolve()
    candidate = (root / raw_name).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_dir():
        return None
    return candidate


@bp.route("/papierkorb")
@login_required
def index():
    root = _trash_root(_content_dir())
    entries = []
    if root.is_dir():
        for child in sorted(root.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            parsed = _parse_entry_name(child.name)
            entries.append({
                "raw_name": child.name,
                "stamp": _format_stamp(parsed[0]) if parsed else "?",
                "visibility": parsed[1] if parsed else "?",
                "dir_name": parsed[2] if parsed else child.name,
                "restorable": parsed is not None,
            })
    return render_template("trash.html", entries=entries)


@bp.route("/papierkorb/<raw_name>/wiederherstellen", methods=["POST"])
@login_required
def restore(raw_name):
    content_dir = _content_dir()
    source = _resolve_trash_entry(content_dir, raw_name)
    if source is None:
        abort(404)

    parsed = _parse_entry_name(raw_name)
    if parsed is None:
        flash("Eintrag hat ein unbekanntes Format und kann nicht automatisch wiederhergestellt werden.", "error")
        return redirect("/papierkorb")

    _stamp, visibility, dir_name = parsed
    target = Path(content_dir) / "beitraege" / visibility / dir_name
    if target.exists():
        flash("Zielverzeichnis existiert bereits — nicht wiederhergestellt.", "error")
        return redirect("/papierkorb")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    versioning.commit_all(Path(content_dir), f"Aus Papierkorb wiederhergestellt: {dir_name}")
    flash("Wiederhergestellt.", "success")
    return redirect("/papierkorb")


@bp.route("/papierkorb/<raw_name>/endgueltig-loeschen", methods=["POST"])
@login_required
def delete_forever(raw_name):
    content_dir = _content_dir()
    target = _resolve_trash_entry(content_dir, raw_name)
    if target is None:
        abort(404)

    shutil.rmtree(target)
    versioning.commit_all(Path(content_dir), f"Endgültig gelöscht: {raw_name}")
    flash("Endgültig gelöscht.", "success")
    return redirect("/papierkorb")
