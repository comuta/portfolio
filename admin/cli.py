"""`flask --app wsgi_admin create-user` — the only way to set up or change
the admin account. Deliberately not reachable over HTTP (FA-26: the
long-running admin service only ever gets read access to zugang/); this
is meant to be run via the admin-cli Compose profile, which mounts
zugang/ read-write.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click
import pyotp
import qrcode
from argon2 import PasswordHasher
from flask import Flask, current_app

from . import users, versioning


def register(app: Flask) -> None:
    app.cli.add_command(create_user)


@click.command("create-user")
@click.option("--force", is_flag=True, help="Vorhandenes Konto überschreiben.")
def create_user(force: bool) -> None:
    """Legt den Admin-Zugang an: Passwort (argon2id) + TOTP-Secret."""
    content_dir = current_app.config["CONTENT_DIR"]

    if users.load_user(content_dir) is not None and not force:
        click.echo("Es existiert bereits ein Konto. --force zum Überschreiben.", err=True)
        raise SystemExit(1)

    benutzername = click.prompt("Benutzername")
    passwort = click.prompt("Passwort", hide_input=True, confirmation_prompt=True)

    hasher = PasswordHasher()
    secret = pyotp.random_base32()

    konto = users.Benutzer(
        benutzername=benutzername,
        passwort_hash=hasher.hash(passwort),
        totp_secret=secret,
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
