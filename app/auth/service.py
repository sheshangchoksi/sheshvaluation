"""
auth/service.py — signup/authenticate against the users table. Mirrors
the pattern from the reference project (sheshscout): timing-safe login
(same work done whether or not the email exists), account lockout after
repeated failures, Argon2 hashing.
"""
from app.auth.lockout import clear_attempts, is_locked_out, record_failed_attempt
from app.auth.models import User
from app.auth.security import DUMMY_HASH, hash_password, verify_password
from app.extensions import db


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class AccountLocked(Exception):
    pass


def signup(email: str, password: str) -> User:
    email = email.strip().lower()
    existing = User.query.filter_by(email=email).first()
    if existing:
        raise EmailAlreadyRegistered(email)

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(email: str, password: str) -> User:
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()

    if user is not None and is_locked_out(user):
        raise AccountLocked(email)

    # Deliberately do the same amount of work, and raise the same error,
    # whether or not the email exists -- don't let timing or message
    # content leak whether an email is registered.
    if user is None or not user.is_active:
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentials(email)

    if not verify_password(password, user.password_hash):
        record_failed_attempt(db, user)
        raise InvalidCredentials(email)

    clear_attempts(db, user)
    return user
