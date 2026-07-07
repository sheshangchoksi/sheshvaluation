"""
auth/lockout.py — slow down brute-force password guessing.

Same fixed-window idea as the reference project's Redis version, but
stored directly on the user row instead — this app doesn't run Redis,
and a small trusted-team app doesn't need sub-millisecond lockout
checks across many processes.
"""
from datetime import datetime, timedelta, timezone

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)


def is_locked_out(user) -> bool:
    if user is None or user.locked_until is None:
        return False
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return now < locked_until


def record_failed_attempt(db, user) -> None:
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= MAX_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + WINDOW
    db.session.commit()


def clear_attempts(db, user) -> None:
    user.failed_attempts = 0
    user.locked_until = None
    db.session.commit()
