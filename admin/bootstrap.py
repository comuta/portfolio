"""First-run setup of the content directory (FA-44-ish, admin-only).

Ensures the directory skeleton exists, optionally seeds it from a demo
content directory on first run (used by Docker Compose for a working
out-of-the-box demo), and makes sure it's a git repo (FA-41).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import versioning

_SKELETON = (
    "beitraege/oeffentlich",
    "beitraege/privat",
    "seiten",
    "zugang",
    ".papierkorb",
)


def ensure_content_dir(content_dir: str, seed_from: str | None = None) -> None:
    base = Path(content_dir)
    is_new = not base.exists() or not any(base.iterdir())

    for rel in _SKELETON:
        (base / rel).mkdir(parents=True, exist_ok=True)

    seed_path = Path(seed_from) if seed_from else None

    if is_new and seed_path:
        _seed(base, seed_path)

    # site.config.json lives alone at the content-dir root (not inside one of
    # the _SKELETON directories), and Docker Compose bind-mounts it as a single
    # file for both services. If the host path doesn't exist yet when a
    # container starts, Docker silently creates it as an empty *directory*
    # instead — so this file has to exist before that first mount happens.
    _ensure_site_config(base, seed_path)

    versioning.ensure_repo(base)


def _seed(base: Path, seed_from: Path) -> None:
    if not seed_from.is_dir():
        return
    for item in seed_from.iterdir():
        target = base / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _ensure_site_config(base: Path, seed_from: Path | None) -> None:
    target = base / "site.config.json"
    if target.exists() or seed_from is None:
        return
    example = seed_from / "site.config.example.json"
    if example.is_file():
        shutil.copy2(example, target)
