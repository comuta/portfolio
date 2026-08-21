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
