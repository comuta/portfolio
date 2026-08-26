from __future__ import annotations

from functools import wraps

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from . import limiter, users

bp = Blueprint("auth", __name__)
_hasher = PasswordHasher()


def _is_recovery_code(konto: users.Benutzer, code: str) -> bool:
    if not konto.recovery_code_hash or not code:
        return False
    try:
        _hasher.verify(konto.recovery_code_hash, code)
        return True
    except VerifyMismatchError:
        return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if session.get("user"):
        return redirect("/")

    content_dir = current_app.config["CONTENT_DIR"]
    konto = users.load_user(content_dir)
    next_path = request.values.get("next") or "/"

    if request.method == "POST":
        if konto is None:
            flash("Noch kein Konto eingerichtet — siehe: flask create-user", "error")
            return render_template("login.html", next_path=next_path), 400

        eingegebener_name = request.form.get("benutzername", "")
        passwort = request.form.get("passwort", "")
        code = request.form.get("code", "")

        gueltig = eingegebener_name == konto.benutzername
        if gueltig:
            try:
                _hasher.verify(konto.passwort_hash, passwort)
            except VerifyMismatchError:
                gueltig = False
        if gueltig:
            gueltig = pyotp.TOTP(konto.totp_secret).verify(code, valid_window=1) or _is_recovery_code(konto, code)

        if not gueltig:
            flash("Anmeldung fehlgeschlagen.", "error")
            return render_template("login.html", next_path=next_path), 401

        session.clear()
        session["user"] = konto.benutzername
        session.permanent = True
        return redirect(next_path if next_path.startswith("/") else "/")

    return render_template("login.html", next_path=next_path)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")
