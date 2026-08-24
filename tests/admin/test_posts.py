from pathlib import Path

from web import create_app as create_web_app


def _new_post_form(**overrides) -> dict:
    data = {
        "titel": "Testprojekt",
        "datum": "2026-08-20",
        "typ": "projekt",
        "status": "abgeschlossen",
        "kurzbeschreibung": "Kurz.",
        "stack": "Flask, nginx",
        "themen": "Test",
        "zeitraum": "",
        "rolle": "",
        "demo_verfuegbar": "",
        "demo_oeffentlich": "",
        "demo_hinweis": "",
        "repository": "",
        "titelbild": "",
        "kunde_nennung_erlaubt": "",
        "kunde_name": "",
        "kunde_bezeichnung_anonym": "",
        "inhalt": "# Hallo\n\nText.",
    }
    data.update(overrides)
    return data


def test_new_post_lands_in_privat(logged_in_client, content_dir):
    resp = logged_in_client.post("/beitraege/neu", data=_new_post_form(), follow_redirects=False)
    assert resp.status_code == 302
    dir_name = resp.headers["Location"].split("/")[2]

    assert (content_dir / "beitraege" / "privat" / dir_name / "meta.json").is_file()
    assert not (content_dir / "beitraege" / "oeffentlich" / dir_name).exists()


def test_full_lifecycle_publish_unpublish_delete_restore(logged_in_client, content_dir):
    resp = logged_in_client.post("/beitraege/neu", data=_new_post_form(), follow_redirects=False)
    dir_name = resp.headers["Location"].split("/")[2]

    privat = content_dir / "beitraege" / "privat" / dir_name
    oeffentlich = content_dir / "beitraege" / "oeffentlich" / dir_name

    logged_in_client.post(f"/beitraege/{dir_name}/veroeffentlichen")
    assert oeffentlich.is_dir() and not privat.exists()

    logged_in_client.post(f"/beitraege/{dir_name}/zurueckziehen")
    assert privat.is_dir() and not oeffentlich.exists()

    logged_in_client.post(f"/beitraege/{dir_name}/loeschen")
    assert not privat.exists()
    trash_entries = list((content_dir / ".papierkorb").iterdir())
    assert len(trash_entries) == 1
    assert dir_name in trash_entries[0].name

    resp = logged_in_client.post(f"/papierkorb/{trash_entries[0].name}/wiederherstellen")
    assert resp.status_code == 302
    assert privat.is_dir()


def test_edit_preserves_dir_name_even_if_title_changes(logged_in_client, content_dir):
    resp = logged_in_client.post("/beitraege/neu", data=_new_post_form(), follow_redirects=False)
    dir_name = resp.headers["Location"].split("/")[2]

    resp = logged_in_client.post(
        f"/beitraege/{dir_name}/bearbeiten", data=_new_post_form(titel="Ganz anderer Titel"), follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/beitraege/{dir_name}/bearbeiten"

    meta = (content_dir / "beitraege" / "privat" / dir_name / "meta.json").read_text()
    assert "Ganz anderer Titel" in meta


def test_edit_unknown_dir_name_is_404(logged_in_client):
    resp = logged_in_client.get("/beitraege/does-not-exist/bearbeiten")
    assert resp.status_code == 404


def test_edit_dir_name_with_traversal_is_404(logged_in_client):
    resp = logged_in_client.get("/beitraege/..%2f..%2f..%2fetc/bearbeiten")
    assert resp.status_code == 404


def test_markdown_preview_is_sanitized(logged_in_client):
    resp = logged_in_client.post("/vorschau", data={"inhalt": "# T\n\n<script>alert(1)</script>"})
    assert resp.status_code == 200
    assert "<script" not in resp.get_data(as_text=True)


def test_invalid_meta_is_reported_not_hidden(logged_in_client, content_dir):
    broken = content_dir / "beitraege" / "oeffentlich" / "2026-08-kaputt"
    broken.mkdir(parents=True)
    (broken / "meta.json").write_text("{not valid json")

    resp = logged_in_client.get("/")
    body = resp.get_data(as_text=True)
    assert "2026-08-kaputt" in body
    assert "Fehler" in body


def test_published_post_is_structurally_invisible_to_web_app_when_privat(logged_in_client, content_dir):
    """FA-03: visibility is enforced by which directory a post lives in — the
    web app must never see a privat/ post, published or not."""
    resp = logged_in_client.post("/beitraege/neu", data=_new_post_form(titel="Geheimprojekt"), follow_redirects=False)
    dir_name = resp.headers["Location"].split("/")[2]
    slug = dir_name.split("-", 2)[-1]

    web_app = create_web_app(content_dir=str(content_dir))
    web_client = web_app.test_client()
    assert web_client.get(f"/projekte/{slug}/").status_code == 404
    assert slug not in web_client.get("/projekte").get_data(as_text=True)

    logged_in_client.post(f"/beitraege/{dir_name}/veroeffentlichen")
    assert web_client.get(f"/projekte/{slug}/").status_code == 200
