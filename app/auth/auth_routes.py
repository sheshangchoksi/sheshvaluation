import os

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.auth.service import AccountLocked, EmailAlreadyRegistered, InvalidCredentials, authenticate, signup

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Optional shared secret gating self-service signup -- set SIGNUP_CODE in
# your environment if this app is reachable at a public URL and you don't
# want strangers registering accounts. Leave unset for fully open signup
# (fine if the URL itself is effectively private).
SIGNUP_CODE = os.environ.get("SIGNUP_CODE", "")


def _promote_if_designated_admin(user):
    """Belt-and-suspenders alongside the startup check in app/__init__.py:
    that one only runs when the process boots, so a brand-new signup for
    the designated admin email wouldn't become admin until the next
    restart/deploy. Checking again on every login/signup closes that gap."""
    from app import ADMIN_EMAIL
    from app.extensions import db

    if user.email == ADMIN_EMAIL and not user.is_admin:
        user.is_admin = True
        db.session.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            user = authenticate(email, password)
            _promote_if_designated_admin(user)
            login_user(user, remember=True)
            next_url = request.args.get("next") or url_for("dcf.home")
            return redirect(next_url)
        except AccountLocked:
            flash("Too many failed attempts. Try again in 15 minutes.", "danger")
        except InvalidCredentials:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup_view():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        code = request.form.get("signup_code", "")

        if SIGNUP_CODE and code != SIGNUP_CODE:
            flash("Invalid signup code.", "danger")
            return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))

        if not email or "@" not in email:
            flash("Enter a valid email address.", "danger")
            return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))

        if password != confirm:
            flash("Passwords don't match.", "danger")
            return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))

        try:
            user = signup(email, password)
        except EmailAlreadyRegistered:
            flash("That email is already registered -- try logging in instead.", "danger")
            return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))

        login_user(user, remember=True)
        _promote_if_designated_admin(user)
        flash("Account created.", "success")
        return redirect(url_for("dcf.home"))

    return render_template("auth/signup.html", require_code=bool(SIGNUP_CODE))


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
