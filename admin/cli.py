"""`flask --app wsgi_admin create-user`/`rotate-recovery-code` — the only
way to set up or change the admin account. Deliberately not reachable over
HTTP (FA-26: the long-running admin service only ever gets read access to
zugang/); meant to be run via the admin-cli Compose profile, which mounts
zugang/ read-write.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

import click
import pyotp
import qrcode
from argon2 import PasswordHasher
from flask import Flask, current_app
from flask.cli import with_appcontext

from . import users, versioning

_hasher = PasswordHasher()


def register(app: Flask) -> None:
    app.cli.add_command(create_user)
    app.cli.add_command(rotate_recovery_code)


def _generate_recovery_code() -> str:
    raw = secrets.token_hex(10)  # 20 hex chars, 80 bits
    return "-".join(raw[i:i + 5] for i in range(0, len(raw), 5))


def _print_recovery_code(code: str) -> None:
    click.echo(f"Wiederherstellungscode: {code}")
    click.echo(
        "Jetzt sicher speichern (z. B. Passwort-Manager) — wird nicht erneut angezeigt.\n"
        "Dieser Code bleibt gültig, bis du ihn per 'rotate-recovery-code' neu erzeugst "
        "(am besten direkt nach jeder Verwendung, da er nicht automatisch verbraucht wird)."
    )


@click.command("create-user")
@click.option("--force", is_flag=True, help="Vorhandenes Konto überschreiben.")
@with_appcontext
def create_user(force: bool) -> None:
    """Legt den Admin-Zugang an: Passwort (argon2id) + TOTP-Secret + Wiederherstellungscode."""
    content_dir = current_app.config["CONTENT_DIR"]

    if users.load_user(content_dir) is not None and not force:
        click.echo("Es existiert bereits ein Konto. --force zum Überschreiben.", err=True)
        raise SystemExit(1)

    benutzername = click.prompt("Benutzername")
    passwort = click.prompt("Passwort", hide_input=True, confirmation_prompt=True)

    secret = pyotp.random_base32()
    recovery_code = _generate_recovery_code()

    konto = users.Benutzer(
        benutzername=benutzername,
        passwort_hash=_hasher.hash(passwort),
        totp_secret=secret,
        recovery_code_hash=_hasher.hash(recovery_code),
        erstellt_am=datetime.now(timezone.utc),
    )
    users.save_user(content_dir, konto)
    versioning.commit_all(Path(content_dir), f"zugang: Konto '{benutzername}' eingerichtet")

    uri = pyotp.TOTP(secret).provisioning_uri(name=benutzername, issuer_name="Portfolio Admin")
    click.echo(f"\nKonto für '{benutzername}' angelegt.")
    click.echo(f"TOTP-Secret (falls der QR-Code nicht scannbar ist): {secret}")
    click.echo(f"otpauth-URI: {uri}\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    qr.make()
    try:
        qr.print_ascii()
    except OSError:
        pass  # no usable terminal (e.g. piped output) — the URI above still works

    click.echo()
    _print_recovery_code(recovery_code)


@click.command("rotate-recovery-code")
@with_appcontext
def rotate_recovery_code() -> None:
    """Erzeugt einen neuen Wiederherstellungscode, ohne Passwort/TOTP zu ändern.

    Für den Fall, dass das TOTP-Gerät verloren geht: mit Passwort + diesem
    Code anmelden (Feld für den TOTP-Code akzeptiert auch den Wiederher-
    stellungscode), danach hier sofort einen neuen erzeugen.
    """
    content_dir = current_app.config["CONTENT_DIR"]
    konto = users.load_user(content_dir)
    if konto is None:
        click.echo("Es existiert noch kein Konto. Zuerst 'create-user' ausführen.", err=True)
        raise SystemExit(1)

    recovery_code = _generate_recovery_code()
    konto.recovery_code_hash = _hasher.hash(recovery_code)
    users.save_user(content_dir, konto)
    versioning.commit_all(Path(content_dir), f"zugang: Wiederherstellungscode für '{konto.benutzername}' erneuert")

    click.echo(f"\nNeuer Wiederherstellungscode für '{konto.benutzername}':")
    _print_recovery_code(recovery_code)
