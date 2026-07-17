import os

import click
from flask import Flask


def create_app(config_object="app.config.Config"):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from app.extensions import cache, db, login_manager, migrate
    cache.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.auth import models  # noqa: F401 -- registers User with SQLAlchemy before create_all/migrations run
    from app.dcf import history_models  # noqa: F401 -- registers ValuationHistory
    from app.dcf import about_models  # noqa: F401 -- registers AboutPage
    from app.dcf import billing_models  # noqa: F401 -- registers AppSettings, Subscription

    from app.auth.auth_routes import bp as auth_bp
    from app.dcf.routes import bp as dcf_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dcf_bp)

    register_cli(app)

    @app.context_processor
    def inject_scout_url():
        # SheshScout is a separate FastAPI/React service (its own DB,
        # its own auth) -- not something that can be merged line-for-line
        # into this Flask codebase. This just gives the navbar a link to
        # wherever it's deployed. Empty by default so the link only shows
        # up once SCOUT_URL is actually set on this service.
        return {"scout_url": os.environ.get("SCOUT_URL", "").rstrip("/")}

    # Idempotent: only creates tables that don't exist yet, never touches or
    # drops existing ones. Without this, adding a new db.Model (like the
    # About page) in code does nothing in production until someone manually
    # runs `flask init-db` or a migration against the live Postgres instance
    # — which is exactly what caused the about_page 500 after this feature
    # shipped. Wrapped in try/except so a DB hiccup at boot can't crash the
    # whole app; the error still surfaces per-request via the 500 handler.
    with app.app_context():
        try:
            from app.extensions import db as _db
            _db.create_all()
        except Exception:
            app.logger.exception("db.create_all() failed at startup — tables may be missing")

        # create_all() only creates missing TABLES, not missing COLUMNS on
        # tables that already exist -- so adding is_admin to the existing
        # `users` table needs its own check (same class of bug as the
        # about_page 500: a new field in code doesn't reach prod on its own).
        try:
            _ensure_admin_column(app, _db)
            _promote_designated_admin(_db)
        except Exception:
            app.logger.exception("Admin-column setup failed at startup")

        try:
            _ensure_appsettings_upi_columns(app, _db)
        except Exception:
            app.logger.exception("app_settings UPI-column setup failed at startup")

    @app.route("/favicon.ico")
    def favicon_ico():
        # Some browsers (and bookmark/tab-icon logic) request /favicon.ico
        # directly at the root before ever parsing <link rel="icon"> in
        # <head> -- without this route that request 404s even though the
        # tags in base.html are correct.
        from flask import send_from_directory
        return send_from_directory(
            os.path.join(app.root_path, "static", "img"), "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("error.html", code=403, message="You don't have permission to do that."), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("error.html", code=500, message="Something went wrong."), 500

    return app


# The one account that should always be admin. Overridable via env var so
# this isn't hardcoded if the real owner's email ever changes, but defaults
# to the address that was explicitly asked to be admin.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "sheshang2004@gmail.com").strip().lower()


def _ensure_admin_column(app, db):
    """Add users.is_admin if it's missing (existing table, so create_all()
    won't touch it). Works on both Postgres (prod) and SQLite (local/dev)."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return  # create_all() above will have made it fresh, with is_admin already
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" in columns:
        return
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
    app.logger.info("Added missing users.is_admin column")


def _ensure_appsettings_upi_columns(app, db):
    """Add app_settings.upi_id / upi_merchant_name if missing (existing
    table from an earlier deploy, so create_all() won't touch it) -- same
    reasoning as _ensure_admin_column above. Without this, an admin who
    deployed before the UPI-ID-editing feature shipped would 500 the first
    time /admin or /billing/pay queried the new columns."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "app_settings" not in inspector.get_table_names():
        return  # create_all() above will have made it fresh, columns included
    columns = {c["name"] for c in inspector.get_columns("app_settings")}
    with db.engine.begin() as conn:
        if "upi_id" not in columns:
            conn.execute(text(
                "ALTER TABLE app_settings ADD COLUMN upi_id VARCHAR(120) NOT NULL DEFAULT 'sheshang304@okaxis'"
            ))
            app.logger.info("Added missing app_settings.upi_id column")
        if "upi_merchant_name" not in columns:
            conn.execute(text(
                "ALTER TABLE app_settings ADD COLUMN upi_merchant_name VARCHAR(120) NOT NULL DEFAULT 'SheshAnalysis'"
            ))
            app.logger.info("Added missing app_settings.upi_merchant_name column")


def _promote_designated_admin(db):
    """Idempotent: if ADMIN_EMAIL has an account, make sure it's an admin.
    Never demotes anyone else -- this only ever adds the flag, never removes
    it, so it's safe to run on every startup."""
    from app.auth.models import User

    user = User.query.filter_by(email=ADMIN_EMAIL).first()
    if user is not None and not user.is_admin:
        user.is_admin = True
        db.session.commit()


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_cmd():
        """One-time setup: creates the users table. Run this once against
        whatever database DATABASE_URL points at (local SQLite by default,
        or Render Postgres in production) -- ordinary schema changes later
        should go through `flask db migrate` / `flask db upgrade` instead
        (Flask-Migrate is already wired up), this command is just for the
        very first table creation.
        """
        from app.extensions import db
        db.create_all()
        print("Database tables created.")

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin_cmd(email):
        """Grant admin rights to an existing account: flask make-admin someone@example.com"""
        from app.extensions import db
        from app.auth.models import User

        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None:
            print(f"No account found for {email} — they need to sign up first.")
            return
        user.is_admin = True
        db.session.commit()
        print(f"{email} is now an admin.")
