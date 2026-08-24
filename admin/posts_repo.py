"""Admin-side post scanning/writing.

Deliberately separate from shared/content.py: that module is the public
site's read-only, slug-keyed, skip-invalid-silently API. Admin needs to
see both beitraege/oeffentlich/ and beitraege/privat/, key posts by their
actual directory name (stable across title edits), and surface parse
errors instead of hiding them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from shared import content

VISIBILITIES = ("oeffentlich", "privat")

_SAFE_DIRNAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLUG_INVALID = re.compile(r"[^a-z0-9]+")


@dataclass
class PostEntry:
    dir_name: str
    visibility: str
    post: content.Post | None
    error: str | None


def _beitraege_root(content_dir: str) -> Path:
    return Path(content_dir) / "beitraege"


def is_safe_dirname(name: str) -> bool:
    return bool(_SAFE_DIRNAME.match(name))


def slugify(text: str) -> str:
    text = text.strip().lower()
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(src, dst)
    text = _SLUG_INVALID.sub("-", text).strip("-")
    return text or "beitrag"


def make_dir_name(content_dir: str, datum: date, titel: str) -> str:
    base = f"{datum:%Y-%m}-{slugify(titel)}"
    root = _beitraege_root(content_dir)
    candidate = base
    n = 2
    while any((root / v / candidate).exists() for v in VISIBILITIES):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def load_entry(entry_dir: Path, visibility: str) -> PostEntry:
    meta_path = entry_dir / "meta.json"
    if not meta_path.is_file():
        return PostEntry(entry_dir.name, visibility, None, "meta.json fehlt")
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
        post = content.Post.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return PostEntry(entry_dir.name, visibility, None, str(exc))

    post.dir_name = entry_dir.name
    post.slug = entry_dir.name
    inhalt_path = entry_dir / "inhalt.md"
    if inhalt_path.is_file():
        post.content_html = content.render_markdown(inhalt_path.read_text(encoding="utf-8"))
    return PostEntry(entry_dir.name, visibility, post, None)


def iter_all_posts(content_dir: str) -> list[PostEntry]:
    root = _beitraege_root(content_dir)
    entries: list[PostEntry] = []
    for visibility in VISIBILITIES:
        base = root / visibility
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir():
                entries.append(load_entry(child, visibility))

    entries.sort(key=lambda e: e.post.datum if e.post else date.min, reverse=True)
    return entries


def find_post_dir(content_dir: str, dir_name: str) -> tuple[Path, str] | None:
    if not is_safe_dirname(dir_name):
        return None
    root = _beitraege_root(content_dir)
    for visibility in VISIBILITIES:
        candidate = root / visibility / dir_name
        if candidate.is_dir():
            return candidate, visibility
    return None


def read_inhalt(path: Path) -> str:
    inhalt_path = path / "inhalt.md"
    if not inhalt_path.is_file():
        return ""
    return inhalt_path.read_text(encoding="utf-8")


def post_to_form_values(post: content.Post) -> dict:
    return {
        "titel": post.titel,
        "datum": post.datum.isoformat(),
        "typ": post.typ,
        "status": post.status or "",
        "kurzbeschreibung": post.kurzbeschreibung,
        "stack": ", ".join(post.stack),
        "themen": ", ".join(post.themen),
        "zeitraum": post.zeitraum or "",
        "rolle": post.rolle or "",
        "demo_verfuegbar": "on" if (post.demo and post.demo.verfuegbar) else "",
        "demo_oeffentlich": "on" if (post.demo and post.demo.oeffentlich) else "",
        "demo_hinweis": (post.demo.hinweis if post.demo else "") or "",
        "repository": post.repository or "",
        "titelbild": post.titelbild or "",
        "kunde_nennung_erlaubt": "on" if (post.kunde and post.kunde.nennung_erlaubt) else "",
        "kunde_bezeichnung_anonym": (post.kunde.bezeichnung_anonym if post.kunde else "") or "",
        "kunde_name": (post.kunde.name if post.kunde else "") or "",
    }


def parse_form(form) -> dict:
    def split_csv(key: str) -> list[str]:
        raw = form.get(key, "")
        return [item.strip() for item in raw.split(",") if item.strip()]

    demo = None
    if form.get("demo_verfuegbar"):
        demo = {
            "verfuegbar": True,
            "oeffentlich": bool(form.get("demo_oeffentlich")),
            "hinweis": form.get("demo_hinweis") or None,
        }

    kunde = None
    if form.get("kunde_bezeichnung_anonym") or form.get("kunde_name"):
        kunde = {
            "nennung_erlaubt": bool(form.get("kunde_nennung_erlaubt")),
            "bezeichnung_anonym": form.get("kunde_bezeichnung_anonym") or None,
            "name": form.get("kunde_name") or None,
        }

    return {
        "titel": form.get("titel", "").strip(),
        "datum": form.get("datum") or date.today().isoformat(),
        "typ": form.get("typ", "projekt"),
        "status": form.get("status") or None,
        "kurzbeschreibung": form.get("kurzbeschreibung", "").strip(),
        "stack": split_csv("stack"),
        "themen": split_csv("themen"),
        "zeitraum": form.get("zeitraum") or None,
        "rolle": form.get("rolle") or None,
        "demo": demo,
        "repository": form.get("repository") or None,
        "titelbild": form.get("titelbild") or None,
        "kunde": kunde,
    }
