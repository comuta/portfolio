import json
from pathlib import Path

import pytest

from web import create_app


def write_post(base: Path, dir_name: str, meta: dict, inhalt: str = "Text.") -> Path:
    post_dir = base / "beitraege" / "oeffentlich" / dir_name
    post_dir.mkdir(parents=True, exist_ok=True)
    (post_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (post_dir / "inhalt.md").write_text(inhalt, encoding="utf-8")
    return post_dir


@pytest.fixture
def content_dir(tmp_path) -> Path:
    (tmp_path / "seiten").mkdir(parents=True)
    (tmp_path / "seiten" / "impressum.md").write_text("Impressumstext.", encoding="utf-8")
    (tmp_path / "seiten" / "datenschutz.md").write_text("Datenschutztext.", encoding="utf-8")
    (tmp_path / "seiten" / "ueber-mich.md").write_text("Über-mich-Text.", encoding="utf-8")
    (tmp_path / "site.config.json").write_text(json.dumps({
        "name": "TEST NAME",
        "kontakt": {"email": "test@example.dev"},
        "impressum": {"name": "Test Name", "anschrift": "Teststraße 1", "email": "test@example.dev"},
    }), encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(content_dir):
    return create_app(content_dir=str(content_dir))


@pytest.fixture
def client(app):
    return app.test_client()
