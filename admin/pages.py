from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request
from pydantic import ValidationError

from shared import content

from . import media, storage, versioning
from .auth import login_required

bp = Blueprint("pages", __name__)

_PAGE_NAMES = ("impressum", "datenschutz", "ueber-mich")
_PAGE_TITLES = {
    "impressum": "Impressum",
    "datenschutz": "Datenschutzerklärung",
    "ueber-mich": "Über mich",
}
_PORTRAIT_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif")
# Blank rows appended after existing aliases so there's usually room to add
# one or two more without needing the JS "+ weitere Zeile" button at all —
# that button (admin.js) clones rows for anything beyond this.
_SPARE_ALIAS_ROWS = 2


def _content_dir() -> str:
    return current_app.config["CONTENT_DIR"]


def _find_portrait_ext(content_dir: str) -> str | None:
    seiten = Path(content_dir) / "seiten"
    for ext in _PORTRAIT_EXTENSIONS:
        if (seiten / f"portrait.{ext}").is_file():
            return ext
    return None


@bp.route("/seiten")
@login_required
def pages_index():
    return render_template("pages_index.html", pages=[(n, _PAGE_TITLES[n]) for n in _PAGE_NAMES])


@bp.route("/seiten/<name>", methods=["GET", "POST"])
@login_required
def edit_page(name):
    if name not in _PAGE_NAMES:
        abort(404)

    content_dir = _content_dir()
    path = Path(content_dir) / "seiten" / f"{name}.md"

    if request.method == "POST":
        storage.atomic_write_text(path, request.form.get("inhalt", ""))
        versioning.commit_all(Path(content_dir), f"Seite bearbeitet: {name}")
        flash("Seite gespeichert.", "success")
        return redirect(f"/seiten/{name}")

    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    portrait_ext = _find_portrait_ext(content_dir) if name == "ueber-mich" else None
    return render_template(
        "page_form.html", name=name, title=_PAGE_TITLES[name], inhalt=text, portrait_ext=portrait_ext
    )


@bp.route("/seiten/portrait/hochladen", methods=["POST"])
@login_required
def upload_portrait():
    content_dir = _content_dir()
    file_storage = request.files.get("datei")
    if file_storage is None:
        return {"error": "Keine Datei übermittelt."}, 400

    try:
        filename = media.save_validated_image_as(file_storage, Path(content_dir) / "seiten", "portrait")
    except media.UploadError as exc:
        return {"error": str(exc)}, 400

    versioning.commit_all(Path(content_dir), "Porträt aktualisiert")
    return {"pfad": filename}


@bp.route("/einstellungen", methods=["GET", "POST"])
@login_required
def settings():
    content_dir = _content_dir()
    path = Path(content_dir) / "site.config.json"
    existing = content.load_site_config(content_dir)

    if request.method == "POST":
        if _impressum_changed(existing, request.form) and not request.form.get("impressum_bestaetigt"):
            flash("Änderungen am Impressum müssen gesondert bestätigt werden (Häkchen unten im Formular).", "error")
            return render_template("settings_form.html", values=_error_form_values(request.form)), 400

        try:
            data = _parse_settings_form(request.form)
            config = content.SiteConfig.model_validate(data)
        except ValidationError as exc:
            flash(f"Ungültige Eingabe: {exc}", "error")
            return render_template("settings_form.html", values=_error_form_values(request.form)), 400

        storage.atomic_write_json(path, config.model_dump(mode="json"))
        versioning.commit_all(Path(content_dir), "site.config.json aktualisiert")
        flash("Einstellungen gespeichert.", "success")
        return redirect("/einstellungen")

    values = _config_to_form_values(existing) if existing else {"aliase": _blank_alias_rows(_SPARE_ALIAS_ROWS)}
    return render_template("settings_form.html", values=values)


def _blank_alias_rows(count: int) -> list[dict]:
    return [{"plattform": "", "anzeige": "", "url": ""} for _ in range(count)]


def _alias_rows_from_form(form) -> list[dict]:
    """Aliase are submitted as same-named repeated fields (alias_plattform,
    alias_anzeige, alias_url), one triple per row — not indexed field names —
    so there's no hardcoded row count on either the form or the server."""
    plattformen = form.getlist("alias_plattform")
    anzeigenamen = form.getlist("alias_anzeige")
    urls = form.getlist("alias_url")
    return [
        {"plattform": p, "anzeige": a, "url": u}
        for p, a, u in zip(plattformen, anzeigenamen, urls)
    ]


def _error_form_values(form) -> dict:
    """Rebuild the values dict for re-rendering after a failed submission —
    scalar fields survive via plain dict lookup, aliase need the same
    row-reconstruction as a real save plus a couple of spare blank rows."""
    values = form.to_dict()
    values["aliase"] = _alias_rows_from_form(form) + _blank_alias_rows(_SPARE_ALIAS_ROWS)
    return values


def _parse_settings_form(form) -> dict:
    aliase = []
    for row in _alias_rows_from_form(form):
        plattform = row["plattform"].strip()
        anzeige = row["anzeige"].strip()
        url = row["url"].strip() or None
        if plattform or anzeige:
            aliase.append({"anzeige": anzeige, "plattform": plattform, "url": url})

    return {
        "name": form.get("name", "").strip(),
        "aliase": aliase,
        "kurzprofil": form.get("kurzprofil", "").strip(),
        "hinweis": form.get("hinweis", "").strip() or None,
        "verfuegbarkeit": {
            "anzeigen": bool(form.get("verfuegbarkeit_anzeigen")),
            "text": form.get("verfuegbarkeit_text", "").strip() or None,
        },
        "kontakt": {
            "email": form.get("kontakt_email", "").strip(),
            "pgp": form.get("kontakt_pgp", "").strip() or None,
        },
        "impressum": {
            "name": form.get("impressum_name", "").strip(),
            "anschrift": form.get("impressum_anschrift", "").strip(),
            "email": form.get("impressum_email", "").strip(),
            "telefon": form.get("impressum_telefon", "").strip() or None,
            "ust_id": form.get("impressum_ust_id", "").strip() or None,
        },
    }


def _config_to_form_values(config: content.SiteConfig) -> dict:
    values: dict[str, object] = {
        "name": config.name,
        "kurzprofil": config.kurzprofil,
        "hinweis": config.hinweis or "",
        "verfuegbarkeit_anzeigen": "on" if config.verfuegbarkeit.anzeigen else "",
        "verfuegbarkeit_text": config.verfuegbarkeit.text or "",
        "kontakt_email": config.kontakt.email,
        "kontakt_pgp": config.kontakt.pgp or "",
        "impressum_name": config.impressum.name,
        "impressum_anschrift": config.impressum.anschrift,
        "impressum_email": config.impressum.email,
        "impressum_telefon": config.impressum.telefon or "",
        "impressum_ust_id": config.impressum.ust_id or "",
    }
    values["aliase"] = [
        {"plattform": a.plattform, "anzeige": a.anzeige, "url": a.url or ""} for a in config.aliase
    ] + _blank_alias_rows(_SPARE_ALIAS_ROWS)
    return values


def _impressum_changed(existing: content.SiteConfig | None, form) -> bool:
    if existing is None:
        return True
    current = {
        "name": existing.impressum.name,
        "anschrift": existing.impressum.anschrift,
        "email": existing.impressum.email,
        "telefon": existing.impressum.telefon or "",
        "ust_id": existing.impressum.ust_id or "",
    }
    submitted = {
        "name": form.get("impressum_name", "").strip(),
        "anschrift": form.get("impressum_anschrift", "").strip(),
        "email": form.get("impressum_email", "").strip(),
        "telefon": form.get("impressum_telefon", "").strip(),
        "ust_id": form.get("impressum_ust_id", "").strip(),
    }
    return current != submitted
