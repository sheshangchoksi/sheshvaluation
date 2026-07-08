import os

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

    from app.auth.routes import bp as auth_bp
    from app.dcf.routes import bp as dcf_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dcf_bp)

    register_cli(app)

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("error.html", code=500, message="Something went wrong."), 500

    return app


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
