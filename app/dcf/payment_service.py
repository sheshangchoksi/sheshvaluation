"""
UPI payment requests -- dynamic QR code, fixed amount, unique reference.

Same shape as the Streamlit PaymentManager: no payment-gateway merchant
account, so there's no webhook telling this app that money actually
arrived. What this DOES give you, same as before:
  - a unique transaction reference per request (embedded in the UPI
    payment note, so it shows up in your bank/UPI app's transaction list)
  - a dynamically generated QR code encoding your UPI ID + the exact
    amount for that plan -- the payer never types a number
  - a pending-requests queue the admin panel can approve/reject

Approving a request is the one manual step; it's what actually grants the
subscription/credits (see billing_service.grant_subscription/grant_credits).
"""
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote

import qrcode

from app.dcf.billing_models import PaymentRequest
from app.extensions import db

# Fallback default -- only used the first time the AppSettings row is
# created (see billing_models.AppSettings.upi_id). After that, the UPI ID
# actually used for QR codes/links lives in the database and is editable
# from the admin panel (Admin > Quota & Pricing > UPI Payment Details),
# so it can be changed without a redeploy.
UPI_ID = os.environ.get("UPI_ID", "sheshang304@okaxis")
MERCHANT_NAME = os.environ.get("UPI_MERCHANT_NAME", "SheshValuation")

PLAN_LABELS = {
    "1_month": "1 Month Premium",
    "3_month": "3 Month Premium",
    "extra_valuation": "Extra Valuation",
}


def generate_transaction_ref():
    return f"SV-{secrets.token_hex(4).upper()}"


def build_upi_link(amount_inr, transaction_ref, plan_label, upi_id=None, merchant_name=None):
    """upi://pay?pa=<vpa>&pn=<name>&am=<amount>&cu=INR&tn=<note>&tr=<ref>

    `tr` (transaction reference) and the ref embedded in `tn` (note) are
    both non-authoritative on a personal VPA -- some UPI apps show `tn` in
    the recipient's transaction history, others don't -- so the note is
    written to be self-explanatory even on apps that only show that much.

    upi_id/merchant_name default to the env-var fallbacks above, but
    callers should pass the live values from AppSettings (get_settings())
    so an admin's change takes effect immediately.
    """
    upi_id = upi_id or UPI_ID
    merchant_name = merchant_name or MERCHANT_NAME
    note = f"{merchant_name} {plan_label} ref {transaction_ref}"
    params = {
        "pa": upi_id,
        "pn": merchant_name,
        "am": str(amount_inr),
        "cu": "INR",
        "tn": note,
        "tr": transaction_ref,
    }
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"upi://pay?{query}"


def qr_png_bytes(upi_link):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(upi_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def create_payment_request(user_id, plan, amount_inr):
    ref = generate_transaction_ref()
    req = PaymentRequest(user_id=user_id, plan=plan, amount_inr=amount_inr, transaction_ref=ref)
    db.session.add(req)
    db.session.commit()
    return req


def get_request(transaction_ref):
    return PaymentRequest.query.filter_by(transaction_ref=transaction_ref).first()


def list_pending():
    from app.auth.models import User

    reqs = (
        PaymentRequest.query
        .filter_by(status="pending")
        .order_by(PaymentRequest.created_at.asc())
        .all()
    )
    for r in reqs:
        u = db.session.get(User, r.user_id)
        r.user_email = u.email if u else "(deleted user)"
    return reqs


def list_for_user(user_id, limit=20):
    return (
        PaymentRequest.query
        .filter_by(user_id=user_id)
        .order_by(PaymentRequest.created_at.desc())
        .limit(limit)
        .all()
    )


def approve_request(transaction_ref, admin_id):
    from app.dcf.billing_service import grant_credits, grant_subscription

    req = get_request(transaction_ref)
    if req is None or req.status != "pending":
        return False, "Request not found or already resolved."

    if req.plan in ("1_month", "3_month"):
        grant_subscription(req.user_id, req.plan)
    elif req.plan == "extra_valuation":
        grant_credits(req.user_id, 1)

    req.status = "verified"
    req.resolved_at = datetime.now(timezone.utc)
    req.resolved_by = admin_id
    db.session.commit()
    return True, None


def reject_request(transaction_ref, admin_id):
    req = get_request(transaction_ref)
    if req is None or req.status != "pending":
        return False, "Request not found or already resolved."
    req.status = "rejected"
    req.resolved_at = datetime.now(timezone.utc)
    req.resolved_by = admin_id
    db.session.commit()
    return True, None
