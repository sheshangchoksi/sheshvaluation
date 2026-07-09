import functools

from flask import abort
from flask_login import current_user, login_required


def admin_required(view_fn):
    """Like @login_required, but also 403s non-admin accounts. Stack it
    under @login_required (or use alone -- it checks current_user itself)."""

    @login_required
    @functools.wraps(view_fn)
    def wrapped(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view_fn(*args, **kwargs)

    return wrapped
