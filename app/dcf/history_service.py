import json

import numpy as np

from app.dcf.history_models import ValuationHistory
from app.extensions import db


class _JSONSafeEncoder(json.JSONEncoder):
    """Result dicts contain numpy scalars/arrays from pandas-derived
    calculations -- plain json.dumps chokes on those."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)


def _to_float(value):
    """Coerce numpy scalars (and anything else numeric) to a plain Python
    float so they can be bound safely as SQL parameters. Returns None if
    the value is missing or not convertible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def save_history(user_id, mode, result, params):
    entry = ValuationHistory(
        user_id=user_id,
        mode=mode,
        company_name=result.get("company_name", "Unknown"),
        ticker=result.get("ticker") or params.get("ticker"),
        fair_value_per_share=_to_float(
            (result.get("valuation") or {}).get("fair_value_per_share")
            or (result.get("fcfe_valuation") or {}).get("fair_value_per_share")
        ),
        current_price=_to_float(result.get("current_price", 0)),
        wacc=_to_float((result.get("wacc_details") or {}).get("wacc")),
        is_bank_valuation=bool(result.get("is_bank_valuation")),
        result_json=json.dumps(result, cls=_JSONSafeEncoder),
        params_json=json.dumps(params, cls=_JSONSafeEncoder, default=str),
    )
    db.session.add(entry)
    db.session.commit()
    return entry.id


def list_history(user_id, limit=50, search=None):
    query = ValuationHistory.query.filter_by(user_id=user_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                ValuationHistory.company_name.ilike(like),
                ValuationHistory.ticker.ilike(like),
                ValuationHistory.mode.ilike(like),
            )
        )
    return query.order_by(ValuationHistory.created_at.desc()).limit(limit).all()


def delete_history_entry(user_id, entry_id):
    entry = db.session.get(ValuationHistory, entry_id)
    if entry is None or entry.user_id != user_id:
        return False
    db.session.delete(entry)
    db.session.commit()
    return True


def get_history_entry(user_id, entry_id):
    entry = db.session.get(ValuationHistory, entry_id)
    if entry is None or entry.user_id != user_id:
        return None
    return entry
