"""The single admin account (FA-21), stored at zugang/benutzer.json.

Deliberately a single record, not a list — the doc is explicit that this
system has exactly one operator.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from . import storage

_BENUTZER_PATH = "zugang/benutzer.json"


class Benutzer(BaseModel):
    benutzername: str
    passwort_hash: str
    totp_secret: str
    erstellt_am: datetime
    # Static, not single-use: the running admin service only has read access
    # to zugang/ (FA-26), so login can't mark a code "consumed" by writing
    # here. Rotate it via `flask rotate-recovery-code` (ideally right after
    # using it) instead of relying on one-time consumption.
    recovery_code_hash: str | None = None


def _path(content_dir: str) -> Path:
    return Path(content_dir) / _BENUTZER_PATH


def load_user(content_dir: str) -> Benutzer | None:
    path = _path(content_dir)
    if not path.is_file():
        return None
    try:
        return Benutzer.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def save_user(content_dir: str, benutzer: Benutzer) -> None:
    path = _path(content_dir)
    storage.atomic_write_json(path, benutzer.model_dump(mode="json"))
    os.chmod(path, 0o600)
