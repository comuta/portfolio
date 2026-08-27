from argon2 import PasswordHasher

from admin import users


def _create_via_cli(app, username="ada", password="pw123456"):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-user"], input=f"{username}\n{password}\n{password}\n")
    assert result.exit_code == 0, result.output
    return result


def test_create_user_generates_a_working_recovery_code(app, content_dir):
    result = _create_via_cli(app)
    assert "Wiederherstellungscode:" in result.output

    line = next(zeile for zeile in result.output.splitlines() if zeile.startswith("Wiederherstellungscode:"))
    code = line.split(":", 1)[1].strip()

    konto = users.load_user(str(content_dir))
    assert konto is not None
    assert konto.recovery_code_hash is not None
    PasswordHasher().verify(konto.recovery_code_hash, code)  # raises on mismatch


def test_rotate_recovery_code_changes_only_the_recovery_code(app, content_dir):
    _create_via_cli(app)
    before = users.load_user(str(content_dir))

    runner = app.test_cli_runner()
    result = runner.invoke(args=["rotate-recovery-code"])
    assert result.exit_code == 0, result.output

    after = users.load_user(str(content_dir))
    assert after.passwort_hash == before.passwort_hash
    assert after.totp_secret == before.totp_secret
    assert after.recovery_code_hash != before.recovery_code_hash


def test_rotate_recovery_code_invalidates_the_old_code(app, content_dir):
    result = _create_via_cli(app)
    old_line = next(zeile for zeile in result.output.splitlines() if zeile.startswith("Wiederherstellungscode:"))
    old_code = old_line.split(":", 1)[1].strip()

    runner = app.test_cli_runner()
    runner.invoke(args=["rotate-recovery-code"])

    konto = users.load_user(str(content_dir))
    try:
        PasswordHasher().verify(konto.recovery_code_hash, old_code)
        raised = False
    except Exception:
        raised = True
    assert raised, "old recovery code should no longer verify after rotation"


def test_rotate_recovery_code_without_existing_account_fails(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["rotate-recovery-code"])
    assert result.exit_code != 0
