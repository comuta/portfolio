from tests.conftest import write_post


def test_unknown_project_slug_returns_custom_404(client):
    resp = client.get("/projekte/does-not-exist/")
    assert resp.status_code == 404
    assert "404" in resp.get_data(as_text=True)


def test_note_slug_is_not_reachable_via_project_detail(content_dir, client):
    write_post(content_dir, "2026-08-eine-notiz", {"titel": "Notiz", "datum": "2026-08-01", "typ": "notiz"})
    resp = client.get("/projekte/eine-notiz/")
    assert resp.status_code == 404


def test_project_detail_redirects_to_trailing_slash(content_dir, client):
    write_post(content_dir, "2026-08-shop-prototyp", {"titel": "Shop", "datum": "2026-08-17", "typ": "projekt"})
    resp = client.get("/projekte/shop-prototyp", follow_redirects=False)
    assert resp.status_code == 308
    assert resp.headers["Location"].endswith("/projekte/shop-prototyp/")


def test_media_route_rejects_path_traversal(content_dir, client):
    post_dir = write_post(content_dir, "2026-08-shop-prototyp", {"titel": "Shop", "datum": "2026-08-17", "typ": "projekt"})
    (post_dir / "medien").mkdir()
    (post_dir / "medien" / "bild.png").write_bytes(b"fake")

    ok = client.get("/projekte/shop-prototyp/medien/bild.png")
    assert ok.status_code == 200

    traversal = client.get("/projekte/shop-prototyp/medien/..%2f..%2f..%2f..%2fetc%2fpasswd")
    assert traversal.status_code == 404


def test_homepage_and_all_pages_are_reachable(content_dir, client):
    write_post(content_dir, "2026-08-shop-prototyp", {"titel": "Shop", "datum": "2026-08-17", "typ": "projekt"})
    write_post(content_dir, "2026-06-eine-notiz", {"titel": "Notiz", "datum": "2026-06-01", "typ": "notiz"})

    for path in ("/", "/projekte", "/notizen", "/ueber-mich", "/impressum", "/datenschutz", "/feed.xml"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_security_headers_are_present(client):
    resp = client.get("/")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in resp.headers


def test_feed_includes_notes_not_just_projects(content_dir, client):
    write_post(content_dir, "2026-08-shop-prototyp", {"titel": "Shop", "datum": "2026-08-17", "typ": "projekt"})
    write_post(content_dir, "2026-06-eine-notiz", {"titel": "Eine Notiz", "datum": "2026-06-01", "typ": "notiz"})

    body = client.get("/feed.xml").get_data(as_text=True)
    assert "Shop" in body
    assert "Eine Notiz" in body


def test_feed_default_limit_and_custom_limit(content_dir, client):
    for i in range(25):
        write_post(content_dir, f"2026-01-projekt-{i:02d}", {
            "titel": f"Projekt {i}", "datum": f"2026-01-{i + 1:02d}", "typ": "projekt",
        })

    default_body = client.get("/feed.xml").get_data(as_text=True)
    assert default_body.count("<entry>") == 20

    limited_body = client.get("/feed.xml?limit=5").get_data(as_text=True)
    assert limited_body.count("<entry>") == 5

    over_max_body = client.get("/feed.xml?limit=9999").get_data(as_text=True)
    assert over_max_body.count("<entry>") == 25  # capped by FEED_MAX_LIMIT, not by entry count here

    invalid_body = client.get("/feed.xml?limit=not-a-number").get_data(as_text=True)
    assert invalid_body.count("<entry>") == 20  # falls back to the default


def test_healthz_ok_when_content_dir_exists(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_healthz_503_when_content_dir_missing():
    from web import create_app

    app = create_app(content_dir="/does/not/exist")
    resp = app.test_client().get("/healthz")
    assert resp.status_code == 503
