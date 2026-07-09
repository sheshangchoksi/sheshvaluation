import uuid
from datetime import datetime, timezone

from flask_login import UserMixin

from app.extensions import db, login_manager


def _uuid_str():
    return str(uuid.uuid4())


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Lockout state kept on the row itself -- no Redis needed for a small,
    # trusted-team app. See auth/lockout.py for the fixed-window logic.
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # UserMixin expects an `is_active` property -- backed by the `is_active`
    # DB column, aliased above to avoid clashing with the Python property name.
    @property
    def is_active(self):
        return self.is_active_flag


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)
