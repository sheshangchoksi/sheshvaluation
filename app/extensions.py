"""
Extensions are created here (uninitialized) and attached to the app
in create_app() via .init_app(). This avoids circular imports between
blueprints and the app factory.
"""
from flask_caching import Cache
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

cache = Cache()
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"
