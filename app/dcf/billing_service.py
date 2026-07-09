from datetime import datetime, timedelta, timezone

from app.dcf.billing_models import IST, AppSettings, Subscription
from app.dcf.history_models import ValuationHistory
from app.extensions import db


def get_settings():
    s = db.session.get(AppSettings, 1)
    if s is None:
        s = AppSettings(id=1)
        db.session.add(s)
        db.session.commit()
    return s


def update_settings(fields):
    s = get_settings()
    for key in ("daily_free_valuations", "price_per_extra_valuation_inr",
                "price_1_month_inr", "price_3_month_inr"):
        if key in fields:
            setattr(s, key, fields[key])
    if "upi_id" in fields and fields["upi_id"]:
        s.upi_id = fields["upi_id"].strip()
    if "upi_merchant_name" in fields and fields["upi_merchant_name"]:
        s.upi_merchant_name = fields["upi_merchant_name"].strip()
    db.session.commit()
    return s


def get_or_create_subscription(user_id):
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if sub is None:
        sub = Subscription(user_id=user_id)
        db.session.add(sub)
        db.session.commit()
    return sub


def _ist_day_start_utc():
    now_ist = datetime.now(IST)
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_ist.astimezone(timezone.utc)


def valuations_used_today(user_id):
    return (
        ValuationHistory.query
        .filter(ValuationHistory.user_id == user_id)
        .filter(ValuationHistory.created_at >= _ist_day_start_utc())
        .count()
    )


def check_quota(user):
    """Returns (allowed: bool, detail: dict) without consuming anything.
    Call this before running a valuation. detail always includes
    free_limit, used_today, remaining_free, credits, is_premium, so the
    form/flash message can explain exactly why (or why not)."""
    settings = get_settings()

    if getattr(user, "is_admin", False):
        return True, {"reason": "admin", "unlimited": True}

    sub = get_or_create_subscription(user.id)
    if sub.is_premium_active:
        return True, {"reason": "premium", "unlimited": True, "active_until": sub.active_until}

    used = valuations_used_today(user.id)
    remaining_free = max(0, settings.daily_free_valuations - used)
    if remaining_free > 0:
        return True, {"reason": "free_quota", "remaining_free": remaining_free - 1, "used_today": used}

    if sub.extra_credits > 0:
        return True, {"reason": "credit", "credits_remaining_after": sub.extra_credits - 1}

    return False, {
        "reason": "quota_exceeded",
        "free_limit": settings.daily_free_valuations,
        "used_today": used,
        "price_per_extra": settings.price_per_extra_valuation_inr,
        "price_1_month": settings.price_1_month_inr,
        "price_3_month": settings.price_3_month_inr,
    }


def consume_credit_if_needed(user, quota_detail):
    """Call right after check_quota() returned allowed=True. If that
    allowance came from a paid credit (not the free daily quota or
    premium), decrement the balance now."""
    if quota_detail.get("reason") == "credit":
        sub = get_or_create_subscription(user.id)
        if sub.extra_credits > 0:
            sub.extra_credits -= 1
            db.session.commit()


# ---------------------------------------------------------------- admin ---

def grant_credits(user_id, n):
    sub = get_or_create_subscription(user_id)
    sub.extra_credits = max(0, sub.extra_credits + n)
    db.session.commit()
    return sub


def grant_subscription(user_id, plan):
    """plan: '1_month' or '3_month'. Extends from the current active_until
    if still active, otherwise starts from now -- so renewing early doesn't
    lose paid-for time."""
    days = 30 if plan == "1_month" else 90
    sub = get_or_create_subscription(user_id)
    now = datetime.now(timezone.utc)
    base = sub.active_until if (sub.active_until and sub.active_until > now) else now
    sub.active_until = base + timedelta(days=days)
    sub.plan = plan
    db.session.commit()
    return sub


def revoke_subscription(user_id):
    sub = get_or_create_subscription(user_id)
    sub.active_until = None
    sub.plan = None
    db.session.commit()
    return sub


def list_users_with_status():
    from app.auth.models import User

    users = User.query.order_by(User.created_at.asc()).all()
    out = []
    for u in users:
        sub = get_or_create_subscription(u.id)
        out.append({
            "user": u,
            "subscription": sub,
            "used_today": valuations_used_today(u.id),
        })
    return out


def delete_user(user_id, requesting_admin_id):
    from app.auth.models import User

    if user_id == requesting_admin_id:
        return False, "You can't delete your own account while logged in as it."

    target = db.session.get(User, user_id)
    if target is None:
        return False, "User not found."

    if target.is_admin:
        remaining_admins = User.query.filter(User.is_admin.is_(True), User.id != user_id).count()
        if remaining_admins == 0:
            return False, "Can't delete the last remaining admin."

    ValuationHistory.query.filter_by(user_id=user_id).delete()
    Subscription.query.filter_by(user_id=user_id).delete()
    db.session.delete(target)
    db.session.commit()
    return True, None
