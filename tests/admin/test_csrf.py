"""Unlike the rest of tests/admin/, this file deliberately keeps CSRF
protection ON — it's the one place that needs to actually exercise it."""

import re
from datetime import datetime, timezone

import pyotp
import pytest
from argon2 import PasswordHasher

from admin import create_app, limiter, users

PASSWORD = "correct horse battery staple"
USERNAME = "ada"


@pytest.fixture
def csrf_app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    flask_app = create_app(content_dir=str(tmp_path))
    flask_app.config["TESTING"] = True

    totp_secret = pyotp.random_base32()
    with flask_app.app_context():
        konto = users.Benutzer(
            benutzername=USERNAME,
            passwort_hash=PasswordHasher().hash(PASSWORD),
            totp_secret=totp_secret,
            erstellt_am=datetime.now(timezone.utc),
        )
        users.save_user(str(tmp_path), konto)

    return flask_app, totp_secret


@pytest.fixture(autouse=True)
def _reset_rate_limiter(csrf_app):
    limiter.reset()
    yield


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "no csrf_token field found in response"
    return match.group(1)


def test_login_without_csrf_token_is_rejected(csrf_app):
    app, _secret = csrf_app
    client = app.test_client()
    resp = client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": "000000"})
    assert resp.status_code == 400


def test_login_with_valid_csrf_token_succeeds(csrf_app):
    app, secret = csrf_app
    client = app.test_client()

    login_page = client.get("/login")
    token = _extract_csrf_token(login_page.get_data(as_text=True))

    code = pyotp.TOTP(secret).now()
    resp = client.post(
        "/login",
        data={"benutzername": USERNAME, "passwort": PASSWORD, "code": code, "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_state_changing_post_without_csrf_token_is_rejected_even_when_logged_in(csrf_app):
    app, secret = csrf_app
    client = app.test_client()

    login_page = client.get("/login")
    token = _extract_csrf_token(login_page.get_data(as_text=True))
    code = pyotp.TOTP(secret).now()
    client.post(
        "/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": code, "csrf_token": token}
    )

    resp = client.post("/beitraege/neu", data={"titel": "x", "datum": "2026-08-20", "typ": "projekt", "inhalt": ""})
    assert resp.status_code == 400
