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


def save_history(user_id, mode, result, params):
    entry = ValuationHistory(
        user_id=user_id,
        mode=mode,
        company_name=result.get("company_name", "Unknown"),
        ticker=result.get("ticker") or params.get("ticker"),
        fair_value_per_share=(result.get("valuation") or {}).get("fair_value_per_share")
            or (result.get("fcfe_valuation") or {}).get("fair_value_per_share"),
        current_price=result.get("current_price", 0),
        wacc=(result.get("wacc_details") or {}).get("wacc"),
        is_bank_valuation=bool(result.get("is_bank_valuation")),
        result_json=json.dumps(result, cls=_JSONSafeEncoder),
        params_json=json.dumps(params, cls=_JSONSafeEncoder, default=str),
    )
    db.session.add(entry)
    db.session.commit()
    return entry.id


def list_history(user_id, limit=50):
    return (
        ValuationHistory.query
        .filter_by(user_id=user_id)
        .order_by(ValuationHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def get_history_entry(user_id, entry_id):
    entry = db.session.get(ValuationHistory, entry_id)
    if entry is None or entry.user_id != user_id:
        return None
    return entry
