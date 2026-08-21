import json

from app import content
from tests.conftest import write_post


def test_get_post_unknown_slug_returns_none(content_dir):
    assert content.get_post(str(content_dir), "does-not-exist") is None
    # A slug that looks like a traversal attempt must not resolve to anything either.
    assert content.get_post(str(content_dir), "../../../../etc/passwd") is None


def test_valid_post_is_loaded_and_resolvable_by_slug(content_dir):
    write_post(content_dir, "2026-08-shop-prototyp", {
        "titel": "Shop Prototyp",
        "datum": "2026-08-17",
        "typ": "projekt",
    })

    post = content.get_post(str(content_dir), "shop-prototyp")
    assert post is not None
    assert post.titel == "Shop Prototyp"


def test_invalid_meta_json_is_skipped_not_fatal(content_dir, caplog):
    # Missing required field "typ" -> Pydantic ValidationError.
    write_post(content_dir, "2026-08-kaputt", {
        "titel": "Kaputter Beitrag",
        "datum": "2026-08-17",
    })
    write_post(content_dir, "2026-08-gut", {
        "titel": "Guter Beitrag",
        "datum": "2026-08-16",
        "typ": "projekt",
    })

    with caplog.at_level("WARNING"):
        posts = content.load_posts(str(content_dir))

    assert "gut" in posts
    assert "kaputt" not in posts
    assert len(posts) == 1
    assert any("invalid post" in message for message in caplog.messages)


def test_malformed_json_is_skipped_not_fatal(content_dir):
    post_dir = content_dir / "beitraege" / "oeffentlich" / "2026-08-nicht-json"
    post_dir.mkdir(parents=True)
    (post_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    posts = content.load_posts(str(content_dir))
    assert posts == {}


def test_duplicate_slug_keeps_first(content_dir):
    write_post(content_dir, "2026-01-a-doppelt", {"titel": "Erster", "datum": "2026-01-01", "typ": "projekt"})
    write_post(content_dir, "2026-02-a-doppelt", {"titel": "Zweiter", "datum": "2026-02-01", "typ": "projekt"})

    posts = content.load_posts(str(content_dir))
    assert len(posts) == 1
    assert posts["a-doppelt"].titel == "Erster"


def test_markdown_output_is_sanitized(content_dir):
    write_post(
        content_dir, "2026-08-mit-script",
        {"titel": "Mit Script", "datum": "2026-08-17", "typ": "projekt"},
        inhalt="# Titel\n\n<script>alert(1)</script>\n\nText.",
    )

    post = content.get_post(str(content_dir), "mit-script")
    assert "<script" not in post.content_html
    assert "<h1>Titel</h1>" in post.content_html


def test_list_projects_and_notes_are_separated_and_sorted(content_dir):
    write_post(content_dir, "2026-01-projekt-a", {"titel": "P", "datum": "2026-01-01", "typ": "projekt"})
    write_post(content_dir, "2026-03-projekt-b", {"titel": "P2", "datum": "2026-03-01", "typ": "projekt"})
    write_post(content_dir, "2026-02-notiz-a", {"titel": "N", "datum": "2026-02-01", "typ": "notiz"})

    projects = content.list_projects(str(content_dir))
    notes = content.list_notes(str(content_dir))

    assert [p.slug for p in projects] == ["projekt-b", "projekt-a"]  # newest first
    assert [n.slug for n in notes] == ["notiz-a"]
