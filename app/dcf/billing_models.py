from datetime import datetime, timedelta, timezone

from app.extensions import db

IST = timezone(timedelta(hours=5, minutes=30))  # business is India-based; day boundaries use IST


class AppSettings(db.Model):
    """Single-row table of admin-editable site settings (quota + pricing)."""

    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)  # always 1
    daily_free_valuations = db.Column(db.Integer, nullable=False, default=3)
    price_per_extra_valuation_inr = db.Column(db.Integer, nullable=False, default=10)
    price_1_month_inr = db.Column(db.Integer, nullable=False, default=100)
    price_3_month_inr = db.Column(db.Integer, nullable=False, default=250)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )


class PaymentRequest(db.Model):
    """A pending (or resolved) UPI payment. Created the moment a user picks
    a plan and gets shown a QR code; stays 'pending' until an admin
    confirms the money actually landed (see PaymentManager docstring in
    payment_service.py for why this step can't be automated without a
    payment-gateway merchant account)."""

    __tablename__ = "payment_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    plan = db.Column(db.String(20), nullable=False)  # "1_month" / "3_month" / "extra_valuation"
    amount_inr = db.Column(db.Integer, nullable=False)
    transaction_ref = db.Column(db.String(40), unique=True, nullable=False, index=True)  # e.g. SV-8F3A21C9
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending / verified / rejected
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)


class Subscription(db.Model):
    """Premium status + pay-per-use credit balance for one user.

    NOTE: nothing in this table is populated by a live payment gateway --
    there is no Razorpay/Stripe integration wired up (that needs real
    merchant credentials this app doesn't have). Rows here are written by
    an admin manually, from the admin panel, after payment is confirmed
    out-of-band (UPI/bank transfer/etc).
    """

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    plan = db.Column(db.String(20), nullable=True)  # "1_month" / "3_month" -- last plan granted, for display only
    active_until = db.Column(db.DateTime(timezone=True), nullable=True)
    extra_credits = db.Column(db.Integer, nullable=False, default=0)  # pay-per-use valuations, admin-granted
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    @property
    def is_premium_active(self):
        if self.active_until is None:
            return False
        until = self.active_until
        if until.tzinfo is None:
            # SQLite drops tzinfo on round-trip even though the column is
            # DateTime(timezone=True) and Postgres (prod) preserves it --
            # values written as UTC come back naive there, so treat a naive
            # value as UTC rather than crashing the comparison below.
            until = until.replace(tzinfo=timezone.utc)
        return until > datetime.now(timezone.utc)
