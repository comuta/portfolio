from datetime import datetime, timezone
from pathlib import Path

import pyotp
import pytest
from argon2 import PasswordHasher

from admin import create_app, limiter, users

PASSWORD = "correct horse battery staple"
USERNAME = "ada"
RECOVERY_CODE = "abcde-fghij-klmno-pqrst"


@pytest.fixture
def content_dir(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def app(content_dir, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    flask_app = create_app(content_dir=str(content_dir))
    flask_app.config["TESTING"] = True
    # CSRF is exercised deliberately in test_csrf.py with its own app instance;
    # disabling it here keeps the rest of the suite focused on app logic.
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture(autouse=True)
def _reset_rate_limiter(app):
    # The Limiter instance is a module-level singleton (needed so all
    # blueprints can import the same one); its in-memory storage would
    # otherwise leak failed-login counts between tests. Depending on `app`
    # guarantees limiter.init_app() has already run (storage exists) before
    # we try to reset it.
    limiter.reset()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def totp_secret() -> str:
    return pyotp.random_base32()


@pytest.fixture
def account(app, content_dir, totp_secret):
    with app.app_context():
        konto = users.Benutzer(
            benutzername=USERNAME,
            passwort_hash=PasswordHasher().hash(PASSWORD),
            totp_secret=totp_secret,
            recovery_code_hash=PasswordHasher().hash(RECOVERY_CODE),
            erstellt_am=datetime.now(timezone.utc),
        )
        users.save_user(str(content_dir), konto)
    return konto


@pytest.fixture
def logged_in_client(client, account, totp_secret):
    code = pyotp.TOTP(totp_secret).now()
    client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": code})
    return client
