import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
RENDER_SECRETS_DIR = "/etc/secrets"


def _screener_cookies_path():
    """Prefers a Render Secret File (plaintext-only, so JSON) at
    /etc/secrets/screener_cookies.json, then a local JSON or pickle file
    in instance/ for development."""
    for candidate in (
        os.path.join(RENDER_SECRETS_DIR, "screener_cookies.json"),
        os.path.join(BASE_DIR, "instance", "screener_cookies.json"),
        os.path.join(BASE_DIR, "instance", "screener_cookies.pkl"),
    ):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(BASE_DIR, "instance", "screener_cookies.json")


class Config:
    # Flask needs this to sign session cookies. In production this MUST be
    # set via an environment variable — the fallback here is only so the
    # app doesn't crash on a first local run.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Database — defaults to a local SQLite file so `flask run` works with
    # zero setup. On Render, DATABASE_URL is injected automatically when
    # you attach a Postgres database to this service (see render.yaml).
    _default_sqlite = "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _default_sqlite)
    # Render's Postgres URLs start with "postgres://"; SQLAlchemy 1.4+/2.x
    # requires "postgresql://" — normalize it rather than making every
    # deploy hit this as a surprise.
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cache config (replaces st.cache_data / st.session_state caching).
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = 3600

    # Where uploaded Excel files / generated PDFs are temporarily written.
    # These are deleted right after use in every route, so ephemeral
    # (non-persistent) storage is fine here — no Render disk needed.
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", os.path.join(BASE_DIR, "instance", "uploads")
    )
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB, generous for Excel uploads

    # Screener.in auto-download — Secret File pattern (Render Secret Files
    # are plaintext, so JSON — a binary .pkl wouldn't survive being pasted
    # into the dashboard).
    SCREENER_COOKIES_PATH = os.environ.get("SCREENER_COOKIES_PATH", _screener_cookies_path())

    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
