import pyotp

from .conftest import PASSWORD, USERNAME


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
