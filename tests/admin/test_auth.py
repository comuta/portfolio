import pyotp

from .conftest import PASSWORD, RECOVERY_CODE, USERNAME


def test_login_requires_account_to_exist(client):
    resp = client.post("/login", data={"benutzername": "x", "passwort": "x", "code": "000000"})
    assert resp.status_code == 400
    assert "kein Konto" in resp.get_data(as_text=True)


def test_wrong_password_rejected(client, account):
    resp = client.post("/login", data={"benutzername": USERNAME, "passwort": "wrong", "code": "000000"})
    assert resp.status_code == 401


def test_wrong_totp_code_rejected(client, account):
    resp = client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": "000000"})
    assert resp.status_code == 401


def test_correct_login_sets_session_and_redirects(client, account, totp_secret):
    code = pyotp.TOTP(totp_secret).now()
    resp = client.post(
        "/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": code}, follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    with client.session_transaction() as sess:
        assert sess["user"] == USERNAME


def test_logout_clears_session(logged_in_client):
    with logged_in_client.session_transaction() as sess:
        assert sess.get("user") == USERNAME
    resp = logged_in_client.post("/logout", follow_redirects=False)
    assert resp.status_code == 302
    with logged_in_client.session_transaction() as sess:
        assert "user" not in sess


def test_dashboard_requires_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/login")


def test_next_param_is_not_an_open_redirect(client, account, totp_secret):
    code = pyotp.TOTP(totp_secret).now()
    resp = client.post(
        "/login",
        data={"benutzername": USERNAME, "passwort": PASSWORD, "code": code, "next": "https://evil.example/"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_repeated_failed_logins_are_rate_limited(client, account):
    statuses = []
    for _ in range(6):
        resp = client.post("/login", data={"benutzername": USERNAME, "passwort": "wrong", "code": "000000"})
        statuses.append(resp.status_code)
    assert 429 in statuses


def test_login_with_recovery_code_instead_of_totp_succeeds(client, account):
    resp = client.post(
        "/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": RECOVERY_CODE}, follow_redirects=False
    )
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user"] == USERNAME


def test_login_with_wrong_recovery_code_is_rejected(client, account):
    resp = client.post(
        "/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": "wrong-code-entirely"}
    )
    assert resp.status_code == 401


def test_recovery_code_is_static_not_single_use(client, account):
    """Deliberate design choice: the running admin service can't write to
    zugang/ (FA-26), so login can't mark the code consumed. It stays valid
    until rotated via the CLI — verify it really can be used twice."""
    first = client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": RECOVERY_CODE})
    assert first.status_code == 302

    client.post("/logout")

    second = client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": RECOVERY_CODE})
    assert second.status_code == 302


def test_login_without_recovery_code_configured_falls_back_to_totp_only(client, app, content_dir, totp_secret):
    from datetime import datetime, timezone

    from argon2 import PasswordHasher

    from admin import users

    with app.app_context():
        konto = users.Benutzer(
            benutzername=USERNAME,
            passwort_hash=PasswordHasher().hash(PASSWORD),
            totp_secret=totp_secret,
            erstellt_am=datetime.now(timezone.utc),
        )
        users.save_user(str(content_dir), konto)

    resp = client.post("/login", data={"benutzername": USERNAME, "passwort": PASSWORD, "code": "000000"})
    assert resp.status_code == 401


def test_healthz_does_not_require_login(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_healthz_503_when_content_dir_missing(monkeypatch, tmp_path):
    # create_app()'s own bootstrap step would recreate a never-existing path,
    # so simulate the content dir disappearing *after* startup instead (e.g.
    # an unmounted volume) — the more realistic failure this check is for.
    import shutil

    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    from admin import create_app

    content_dir = tmp_path / "content"
    app = create_app(content_dir=str(content_dir))
    shutil.rmtree(content_dir)

    resp = app.test_client().get("/healthz")
    assert resp.status_code == 503
