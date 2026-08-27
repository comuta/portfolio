import io

from PIL import Image


def _new_post(client) -> str:
    resp = client.post(
        "/beitraege/neu",
        data={
            "titel": "Uploadtest", "datum": "2026-08-20", "typ": "projekt",
            "kurzbeschreibung": "", "stack": "", "themen": "", "inhalt": "",
        },
        follow_redirects=False,
    )
    return resp.headers["Location"].split("/")[2]


def _png_bytes() -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_upload_requires_login(client):
    resp = client.post(
        "/beitraege/whatever/medien/hochladen",
        data={"datei": (_png_bytes(), "photo.png")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/login")


def test_valid_image_is_accepted_with_server_generated_name(logged_in_client, content_dir):
    dir_name = _new_post(logged_in_client)
    resp = logged_in_client.post(
        f"/beitraege/{dir_name}/medien/hochladen",
        data={"datei": (_png_bytes(), "../../evil.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    pfad = resp.get_json()["pfad"]
    assert pfad.startswith("medien/")
    assert ".." not in pfad
    assert (content_dir / "beitraege" / "privat" / dir_name / pfad).is_file()


def test_multiple_images_are_accepted_in_one_request(logged_in_client, content_dir):
    dir_name = _new_post(logged_in_client)
    resp = logged_in_client.post(
        f"/beitraege/{dir_name}/medien/hochladen",
        data={"datei": [(_png_bytes(), "eins.png"), (_png_bytes(), "zwei.png")]},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    pfade = resp.get_json()["pfade"]
    assert len(pfade) == 2
    for pfad in pfade:
        assert pfad.startswith("medien/")
        assert (content_dir / "beitraege" / "privat" / dir_name / pfad).is_file()
    assert len({p for p in pfade}) == 2


def test_non_image_content_is_rejected_despite_image_filename(logged_in_client):
    dir_name = _new_post(logged_in_client)
    resp = logged_in_client.post(
        f"/beitraege/{dir_name}/medien/hochladen",
        data={"datei": (io.BytesIO(b"<svg onload=alert(1)></svg>"), "fake.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_svg_upload_is_rejected(logged_in_client):
    """Pillow can't content-verify SVG (it's XML, not raster), and SVG can
    carry scripts — it must never pass, even with a correct-looking extension."""
    dir_name = _new_post(logged_in_client)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    resp = logged_in_client.post(
        f"/beitraege/{dir_name}/medien/hochladen",
        data={"datei": (io.BytesIO(svg), "image.svg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_to_unknown_post_is_404(logged_in_client):
    resp = logged_in_client.post(
        "/beitraege/does-not-exist/medien/hochladen",
        data={"datei": (_png_bytes(), "photo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_portrait_upload_replaces_previous_extension(logged_in_client, content_dir):
    (content_dir / "seiten").mkdir(parents=True, exist_ok=True)
    (content_dir / "seiten" / "portrait.webp").write_bytes(b"stale")

    resp = logged_in_client.post(
        "/seiten/portrait/hochladen",
        data={"datei": (_png_bytes(), "me.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["pfad"] == "portrait.png"
    assert (content_dir / "seiten" / "portrait.png").is_file()
    assert not (content_dir / "seiten" / "portrait.webp").exists()
