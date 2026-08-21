"""File-based content layer.

Reads posts, static pages and site configuration from CONTENT_DIR
(see README / Anforderungskatalog FA-01/FA-02/FA-08). No database.
Everything is cached with functools.lru_cache keyed on file mtime (FA-06),
so edits to content files are picked up without a restart.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import bleach
import markdown as markdown_lib
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?-")

_ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4",
    "ul", "ol", "li",
    "strong", "em", "code", "pre", "blockquote",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "width", "height"],
}


def render_markdown(text: str) -> str:
    """Render Markdown to sanitized HTML (FA-15)."""
    html = markdown_lib.markdown(text, extensions=["fenced_code", "tables"])
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


class Demo(BaseModel):
    verfuegbar: bool = False
    oeffentlich: bool = False
    hinweis: str | None = None


class Kunde(BaseModel):
    nennung_erlaubt: bool = False
    bezeichnung_anonym: str | None = None
    name: str | None = None


class Post(BaseModel):
    """A Beitrag (project or note), matching the meta.json schema (FA-02)."""

    titel: str
    datum: date
    typ: Literal["projekt", "notiz"]
    status: Literal["abgeschlossen", "laufend"] | None = None
    kurzbeschreibung: str = ""
    stack: list[str] = Field(default_factory=list)
    themen: list[str] = Field(default_factory=list)
    zeitraum: str | None = None
    rolle: str | None = None
    demo: Demo | None = None
    repository: str | None = None
    titelbild: str | None = None
    kunde: Kunde | None = None

    # Populated by the loader, not part of meta.json itself.
    slug: str = ""
    dir_name: str = ""
    content_html: str = ""

    @property
    def titelbild_dateiname(self) -> str | None:
        """Bare filename of titelbild, with a leading 'medien/' stripped."""
        if not self.titelbild:
            return None
        name = self.titelbild.removeprefix("medien/")
        if "/" in name or ".." in name:
            logger.warning("suspicious titelbild path %r in post %r, ignoring", self.titelbild, self.slug)
            return None
        return name


class Alias(BaseModel):
    anzeige: str
    plattform: str
    url: str | None = None


class Verfuegbarkeit(BaseModel):
    anzeigen: bool = False
    text: str | None = None


class Kontakt(BaseModel):
    email: str
    pgp: str | None = None


class ImpressumAngaben(BaseModel):
    name: str
    anschrift: str
    email: str
    telefon: str | None = None
    ust_id: str | None = None


class SiteConfig(BaseModel):
    name: str
    aliase: list[Alias] = Field(default_factory=list)
    kurzprofil: str = ""
    verfuegbarkeit: Verfuegbarkeit = Field(default_factory=Verfuegbarkeit)
    kontakt: Kontakt
    impressum: ImpressumAngaben


def _slug_from_dirname(name: str) -> str:
    slug = _DATE_PREFIX.sub("", name)
    return slug or name


@lru_cache(maxsize=256)
def _load_post_cached(
    meta_path: str, meta_mtime: float, content_path: str, content_mtime: float, dir_name: str
) -> Post | None:
    try:
        raw = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        post = Post.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        logger.warning("skipping invalid post %s: %s", meta_path, exc)
        return None

    post.dir_name = dir_name
    post.slug = _slug_from_dirname(dir_name)

    content_file = Path(content_path)
    if content_file.is_file():
        try:
            post.content_html = render_markdown(content_file.read_text(encoding="utf-8"))
        except OSError as exc:
            logger.warning("could not read inhalt.md for %s: %s", meta_path, exc)

    return post


def _iter_post_dirs(content_dir: str) -> list[Path]:
    base = Path(content_dir) / "beitraege" / "oeffentlich"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir())


def load_posts(content_dir: str) -> dict[str, Post]:
    """Load all public posts, keyed by slug. Invalid entries are skipped, not fatal (FA-04)."""
    posts: dict[str, Post] = {}
    for post_dir in _iter_post_dirs(content_dir):
        meta_path = post_dir / "meta.json"
        content_path = post_dir / "inhalt.md"
        if not meta_path.is_file():
            logger.warning("post directory %s has no meta.json, skipping", post_dir)
            continue
        try:
            meta_mtime = meta_path.stat().st_mtime
            content_mtime = content_path.stat().st_mtime if content_path.is_file() else 0.0
        except OSError as exc:
            logger.warning("could not stat post %s: %s", post_dir, exc)
            continue

        post = _load_post_cached(str(meta_path), meta_mtime, str(content_path), content_mtime, post_dir.name)
        if post is None:
            continue
        if post.slug in posts:
            logger.warning("duplicate slug %r (%s), keeping first", post.slug, post_dir)
            continue
        posts[post.slug] = post
    return posts


def get_post(content_dir: str, slug: str) -> Post | None:
    """Resolve a post by slug. Never touches the filesystem with the raw slug (FA-11)."""
    return load_posts(content_dir).get(slug)


def list_projects(content_dir: str) -> list[Post]:
    posts = [p for p in load_posts(content_dir).values() if p.typ == "projekt"]
    return sorted(posts, key=lambda p: p.datum, reverse=True)


def list_notes(content_dir: str) -> list[Post]:
    posts = [p for p in load_posts(content_dir).values() if p.typ == "notiz"]
    return sorted(posts, key=lambda p: p.datum, reverse=True)


@lru_cache(maxsize=8)
def _load_site_config_cached(path: str, mtime: float) -> SiteConfig | None:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return SiteConfig.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        logger.error("invalid site.config.json at %s: %s", path, exc)
        return None


def load_site_config(content_dir: str) -> SiteConfig | None:
    path = Path(content_dir) / "site.config.json"
    if not path.is_file():
        return None
    return _load_site_config_cached(str(path), path.stat().st_mtime)


@lru_cache(maxsize=16)
def _load_page_cached(path: str, mtime: float) -> str:
    return render_markdown(Path(path).read_text(encoding="utf-8"))


def load_page(content_dir: str, name: str) -> str | None:
    """Load and render a static page from seiten/<name>.md. `name` is always a fixed,
    code-supplied value (never user input), so no path-traversal check is needed here."""
    path = Path(content_dir) / "seiten" / f"{name}.md"
    if not path.is_file():
        return None
    return _load_page_cached(str(path), path.stat().st_mtime)
