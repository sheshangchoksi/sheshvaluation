import uuid
from datetime import datetime, timezone

from app.extensions import db


def _uuid_str():
    return str(uuid.uuid4())


class ValuationHistory(db.Model):
    __tablename__ = "valuation_history"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    mode = db.Column(db.String(20), nullable=False)          # listed / unlisted / screener
    company_name = db.Column(db.String(255), nullable=False)
    ticker = db.Column(db.String(50), nullable=True)
    fair_value_per_share = db.Column(db.Float, nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    wacc = db.Column(db.Float, nullable=True)
    is_bank_valuation = db.Column(db.Boolean, nullable=False, default=False)
    result_json = db.Column(db.Text, nullable=False)   # full serialized result dict (JSON string)
    params_json = db.Column(db.Text, nullable=True)    # inputs used, for re-running later
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
