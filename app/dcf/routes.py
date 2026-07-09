import logging
import os
import uuid

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.auth.decorators import admin_required

from app.dcf.errors import ValuationError
from app.dcf.listed_service import defaults_for_exchange, run_listed_valuation
from app.dcf.pdf_service import build_pdf
from app.dcf.screener_service import run_screener_valuation
from app.dcf.unlisted_service import run_unlisted_valuation
from app.extensions import cache
from app.logic import dcf_engine as de
from app.logic.unlisted_template import create_unlisted_template

bp = Blueprint("dcf", __name__, url_prefix="/")
logger = logging.getLogger(__name__)

EXCHANGES = ["NSE", "BSE", "NASDAQ/NYSE", "LSE", "SSE/HKEX", "Other"]


@bp.route("/dcf/pdf/<result_id>")
@login_required
def download_pdf(result_id):
    cached = cache.get(f"result:{result_id}")
    if not cached:
        flash("This result has expired — please re-run the analysis to download a PDF.", "warning")
        return redirect(url_for("dcf.home"))

    mode, result, name, current_price = cached
    try:
        pdf_path = build_pdf(result, name, current_price)
    except Exception:
        logger.exception("PDF generation failed for result_id=%s", result_id)
        flash("Something went wrong generating the PDF. The on-screen results are still valid.", "danger")
        return redirect(url_for("dcf.home"))

    return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))


@bp.route("/history")
@login_required
def history_list():
    from app.dcf.history_service import list_history
    q = request.args.get("q", "").strip()
    entries = list_history(current_user.id, search=q or None)
    return render_template("dcf/history_list.html", entries=entries, q=q)


@bp.route("/history/<entry_id>/delete", methods=["POST"])
@login_required
def history_delete(entry_id):
    from app.dcf.history_service import delete_history_entry
    if delete_history_entry(current_user.id, entry_id):
        flash("Deleted.", "success")
    else:
        flash("Couldn't find that history entry.", "warning")
    return redirect(url_for("dcf.history_list"))


@bp.route("/history/<entry_id>")
@login_required
def history_detail(entry_id):
    import json as _json
    from app.dcf.history_service import get_history_entry

    entry = get_history_entry(current_user.id, entry_id)
    if entry is None:
        flash("History entry not found.", "warning")
        return redirect(url_for("dcf.history_list"))

    result = _json.loads(entry.result_json)
    params = _json.loads(entry.params_json) if entry.params_json else {}

    # Re-cache so "Download PDF" works from a history entry too.
    result_id = uuid.uuid4().hex
    cache.set(f"result:{result_id}", (entry.mode, result, entry.company_name, entry.current_price or 0), timeout=900)

    if entry.is_bank_valuation:
        return render_template("dcf/bank_results.html", r=result, params=params, mode=entry.mode, result_id=result_id, entry_id=entry.id)
    if entry.mode == "listed":
        return render_template("dcf/listed_results.html", r=result, params=params, result_id=result_id, entry_id=entry.id)
    if entry.mode == "unlisted":
        return render_template("dcf/unlisted_results.html", r=result, params=params, result_id=result_id, entry_id=entry.id)
    return render_template("dcf/screener_results.html", r=result, params=params, result_id=result_id, entry_id=entry.id)


@bp.route("/history/<entry_id>/edit")
@login_required
def history_edit(entry_id):
    """'Edit parameters & re-run' — send the user back to the mode's form
    with every field pre-filled from a past run, instead of results being a
    dead end once you've seen them."""
    import json as _json
    from app.dcf.history_service import get_history_entry

    entry = get_history_entry(current_user.id, entry_id)
    if entry is None:
        flash("History entry not found.", "warning")
        return redirect(url_for("dcf.history_list"))

    prefill = _json.loads(entry.params_json) if entry.params_json else {}

    if entry.mode == "listed":
        defaults = defaults_for_exchange(prefill.get("exchange", "NSE"))
        return render_template("dcf/listed_form.html", exchanges=EXCHANGES, defaults=defaults, prefill=prefill)
    if entry.mode == "unlisted":
        return render_template("dcf/unlisted_form.html", prefill=prefill)
    return render_template("dcf/screener_form.html", prefill=prefill)


@bp.route("/about")
@login_required
def about_page():
    from app.dcf.about_service import get_about, photo_base64
    entry = get_about()
    return render_template("dcf/about_view.html", about=entry, photo_b64=photo_base64(entry))


@bp.route("/about/edit", methods=["GET", "POST"])
@admin_required
def about_edit():
    from app.dcf.about_service import get_about, update_about, resize_photo

    if request.method == "GET":
        entry = get_about()
        return render_template("dcf/about_edit.html", about=entry)

    f = request.form
    fields = {
        "name": f.get("name", "").strip(),
        "tagline": f.get("tagline", "").strip(),
        "about_me": f.get("about_me", "").strip(),
        "academics": f.get("academics", "").strip(),
        "experience": f.get("experience", "").strip(),
        "linkedin_url": f.get("linkedin_url", "").strip(),
        "github_url": f.get("github_url", "").strip(),
        "twitter_url": f.get("twitter_url", "").strip(),
        "email": f.get("email", "").strip(),
        "phone": f.get("phone", "").strip(),
        "website_url": f.get("website_url", "").strip(),
    }

    photo_bytes = None
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        try:
            photo_bytes = resize_photo(photo_file)
        except Exception:
            flash("Couldn't process that image — try a standard JPG/PNG.", "danger")

    resume_bytes = None
    resume_filename = None
    resume_file = request.files.get("resume")
    if resume_file and resume_file.filename:
        resume_bytes = resume_file.read()
        resume_filename = resume_file.filename

    update_about(fields, photo_bytes=photo_bytes, resume_bytes=resume_bytes, resume_filename=resume_filename)
    flash("About page updated.", "success")
    return redirect(url_for("dcf.about_page"))


@bp.route("/about/resume")
@login_required
def about_resume():
    from app.dcf.about_service import get_about
    from flask import Response
    entry = get_about()
    if not entry.resume_data:
        flash("No resume uploaded yet.", "warning")
        return redirect(url_for("dcf.about_page"))
    return Response(
        entry.resume_data, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{entry.resume_filename or "resume.pdf"}"'},
    )


@bp.route("/")
@login_required
def home():
    """
    Landing page — mode picker. Mirrors the st.radio("Select Mode:", ...)
    at the top of the old app's main(). Each card below becomes a full
    workflow in later phases.
    """
    modes = [
        {
            "slug": "listed",
            "title": "Listed Company",
            "subtitle": "Yahoo Finance",
            "ready": True,  # Phase 2 — live
        },
        {
            "slug": "unlisted",
            "title": "Unlisted Company",
            "subtitle": "Excel Upload",
            "ready": True,  # Phase 3 — live
        },
        {
            "slug": "screener",
            "title": "Screener Excel Mode",
            "subtitle": "Screener.in Template",
            "ready": True,  # Phase 4 — live
        },
    ]
    return render_template("dashboard.html", modes=modes)


@bp.route("/dcf/<mode>")
@login_required
def mode_placeholder(mode):
    """Placeholder for modes not yet built (Unlisted, Screener — Phase 5)."""
    return render_template("placeholder.html", mode=mode)


@bp.route("/dcf/listed", methods=["GET"])
@login_required
def listed_form():
    defaults = defaults_for_exchange("NSE")
    return render_template("dcf/listed_form.html", exchanges=EXCHANGES, defaults=defaults)


@bp.route("/dcf/listed/defaults/<exchange>", methods=["GET"])
@login_required
def listed_defaults(exchange):
    """Small JSON endpoint the form's JS calls when the exchange dropdown
    changes, so Rf/Rm defaults update without a full page reload."""
    from flask import jsonify
    return jsonify(defaults_for_exchange(exchange))


@bp.route("/dcf/listed/auto-peers", methods=["GET"])
@login_required
def listed_auto_peers():
    """AJAX endpoint backing the 'Auto-fetch peers' button — mirrors the
    old app's peer auto-fetch feature (utils_peer_fetcher.get_industry_peers),
    scoped to what that module actually supports: finding Yahoo Finance
    'similar companies' for the given ticker."""
    ticker = request.args.get("ticker", "").strip()
    exchange_suffix = request.args.get("suffix", "NS").strip()
    if not ticker:
        return jsonify({"error": "Enter a ticker first."}), 400
    try:
        bare_peers = de.get_industry_peers(ticker, max_peers=10)
        suffixed = [f"{p}.{exchange_suffix}" if exchange_suffix else p for p in bare_peers]
        return jsonify({"peers": suffixed})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/dcf/listed/analyze", methods=["POST"])
@login_required
def listed_analyze():
    form = request.form

    def num(name, default=0.0):
        try:
            return float(form.get(name, default) or default)
        except ValueError:
            return default

    def per_year_list(prefix):
        vals = [num(f"{prefix}_yr{i}", 0) for i in range(1, 16)]
        return vals if any(v > 0 for v in vals) else None

    from datetime import datetime as _dt

    def parse_date(name):
        raw = form.get(name, "").strip()
        if not raw:
            return None
        try:
            return _dt.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    try:
        params = {
            "ticker": form.get("ticker", "").strip(),
            "exchange": form.get("exchange", "NSE"),
            "historical_years": int(form.get("historical_years", 3)),
            "projection_years": int(form.get("projection_years", 5)),
            "tax_rate": float(form.get("tax_rate", 25.0)),
            "terminal_growth": float(form.get("terminal_growth", 4.0)),
            "manual_rf_rate": float(form.get("manual_rf_rate", 6.83)),
            "manual_rm_rate": float(form.get("manual_rm_rate", 12.0)),
            "manual_discount_rate": float(form.get("manual_discount_rate", 0) or 0),
            "manual_shares_override": int(form.get("manual_shares_override", 0) or 0),
            "peer_tickers": form.get("peer_tickers", "").strip(),
            "beta_start_date": parse_date("beta_start_date"),
            "beta_end_date": parse_date("beta_end_date"),
            "rev_growth_per_year": per_year_list("rev_growth"),
            "ebitda_margin_per_year": per_year_list("ebitda_margin"),
            "rev_growth_override": num("rev_growth_override", 0),
            "opex_margin_override": num("opex_margin_override", 0),
            "ebitda_margin_override": num("ebitda_margin_override", 0),
            "capex_ratio_override": num("capex_ratio_override", 0),
            "depreciation_rate_override": num("depreciation_rate_override", 0),
            "depreciation_method": form.get("depreciation_method", "Auto"),
            "inventory_days_override": num("inventory_days_override", 0),
            "debtor_days_override": num("debtor_days_override", 0),
            "creditor_days_override": num("creditor_days_override", 0),
            "interest_rate_override": num("interest_rate_override", 0),
            "working_capital_pct_override": num("working_capital_pct_override", 0),
        }
    except (TypeError, ValueError):
        flash("One of the numeric fields couldn't be read — please check your inputs.", "danger")
        return redirect(url_for("dcf.listed_form"))

    if not params["ticker"]:
        flash("Please enter a ticker.", "danger")
        return redirect(url_for("dcf.listed_form"))

    try:
        result = run_listed_valuation(params)
    except ValuationError as e:
        flash(str(e), "danger")
        return redirect(url_for("dcf.listed_form"))
    except Exception:
        logger.exception("Unexpected error running listed valuation for %s", params["ticker"])
        flash(
            "Something went wrong while running the valuation. "
            "Check the ticker and try again.",
            "danger",
        )
        return redirect(url_for("dcf.listed_form"))

    result_id = uuid.uuid4().hex
    from app.dcf.history_service import save_history
    entry_id = save_history(current_user.id, "listed", result, params)
    cache.set(f"result:{result_id}", ("listed", result, params["ticker"], result.get("current_price", 0)), timeout=900)

    if result.get("is_bank_valuation"):
        return render_template("dcf/bank_results.html", r=result, params=params, mode="listed", result_id=result_id, entry_id=entry_id)
    return render_template("dcf/listed_results.html", r=result, params=params, result_id=result_id, entry_id=entry_id)


@bp.route("/dcf/unlisted/template")
@login_required
def unlisted_template():
    data = create_unlisted_template()
    from io import BytesIO
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name="Financials_Template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/dcf/unlisted/fetch-rate", methods=["GET"])
@login_required
def unlisted_fetch_rate():
    """AJAX endpoint backing the 'Fetch' buttons next to the Rf/Rm ticker
    fields — mirrors the old app's get_risk_free_rate/get_market_return
    buttons."""
    kind = request.args.get("kind")  # "rf" or "rm"
    ticker = request.args.get("ticker", "").strip() or None
    try:
        if kind == "rf":
            rate, debug = de.get_risk_free_rate(ticker)
        else:
            rate, debug = de.get_market_return(ticker)
        return jsonify({"rate": rate, "debug": debug})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/dcf/unlisted", methods=["GET"])
@login_required
def unlisted_form():
    return render_template("dcf/unlisted_form.html")


@bp.route("/dcf/unlisted/analyze", methods=["POST"])
@login_required
def unlisted_analyze():
    f = request.form
    excel_file = request.files.get("excel_file")

    if not excel_file or excel_file.filename == "":
        flash("Please upload an Excel file.", "danger")
        return redirect(url_for("dcf.unlisted_form"))

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    saved_name = f"{uuid.uuid4().hex}_{excel_file.filename}"
    saved_path = os.path.join(upload_dir, saved_name)
    excel_file.save(saved_path)

    def num(name, default=0.0):
        try:
            return float(f.get(name, default) or default)
        except ValueError:
            return default

    def integer(name, default=0):
        try:
            return int(f.get(name, default) or default)
        except ValueError:
            return default

    def per_year_list(prefix):
        vals = [num(f"{prefix}_yr{i}", 0) for i in range(1, 16)]
        return vals if any(v > 0 for v in vals) else None

    params = {
        "company_name": f.get("company_name", "").strip(),
        "num_shares": integer("num_shares", 100),
        "tax_rate": num("tax_rate", 25.0),
        "terminal_growth": num("terminal_growth", 4.0),
        "historical_years": integer("historical_years", 3),
        "projection_years": integer("projection_years", 5),
        "manual_rf_rate": num("manual_rf_rate", 6.83),
        "manual_rm_rate": num("manual_rm_rate", 12.0),
        "manual_discount_rate": num("manual_discount_rate", 0),
        "peer_tickers": f.get("peer_tickers", "").strip(),
        "rev_growth_per_year": per_year_list("rev_growth"),
        "ebitda_margin_per_year": per_year_list("ebitda_margin"),
        "run_dcf": f.get("run_dcf") == "on",
        "run_rim": f.get("run_rim") == "on",
        "run_comp": f.get("run_comp") == "on",
        # Advanced projection overrides — 0 means "auto" throughout
        "rev_growth_override": num("rev_growth_override", 0),
        "opex_margin_override": num("opex_margin_override", 0),
        "ebitda_margin_override": num("ebitda_margin_override", 0),
        "capex_ratio_override": num("capex_ratio_override", 0),
        "depreciation_rate_override": num("depreciation_rate_override", 0),
        "depreciation_method": f.get("depreciation_method", "Auto"),
        "inventory_days_override": num("inventory_days_override", 0),
        "debtor_days_override": num("debtor_days_override", 0),
        "creditor_days_override": num("creditor_days_override", 0),
        "interest_rate_override": num("interest_rate_override", 0),
        "working_capital_pct_override": num("working_capital_pct_override", 0),
        # RIM overrides
        "rim_required_return": num("rim_required_return", 0),
        "rim_assumed_roe": num("rim_assumed_roe", 0),
        "rim_terminal_growth": num("rim_terminal_growth", 0),
        "rim_projection_years": integer("rim_projection_years", 0),
    }

    try:
        result = run_unlisted_valuation(saved_path, params)
    except ValuationError as e:
        flash(str(e), "danger")
        return redirect(url_for("dcf.unlisted_form"))
    except Exception:
        logger.exception("Unexpected error running unlisted valuation")
        flash("Something went wrong while running the valuation. Check the Excel file and try again.", "danger")
        return redirect(url_for("dcf.unlisted_form"))
    finally:
        try:
            os.remove(saved_path)
        except OSError:
            pass

    result_id = uuid.uuid4().hex
    from app.dcf.history_service import save_history
    entry_id = save_history(current_user.id, "unlisted", result, params)
    cache.set(f"result:{result_id}", ("unlisted", result, params.get("company_name") or "Company", 0), timeout=900)

    if result.get("is_bank_valuation"):
        return render_template("dcf/bank_results.html", r=result, params=params, mode="unlisted", result_id=result_id, entry_id=entry_id)
    return render_template("dcf/unlisted_results.html", r=result, params=params, result_id=result_id, entry_id=entry_id)


@bp.route("/dcf/screener/template")
@login_required
def screener_template():
    path = os.path.join(current_app.root_path, "data", "Screener_template.xlsx")
    return send_file(path, as_attachment=True, download_name="Screener_template.xlsx")


@bp.route("/dcf/screener/auto-download", methods=["POST"])
@login_required
def screener_auto_download():
    from app.dcf.screener_autodownload_service import auto_download

    f = request.form
    company_symbol = f.get("company_symbol", "").strip()
    if not company_symbol:
        flash("Enter a Screener.in company symbol (e.g. RELIANCE, HONASA).", "danger")
        return redirect(url_for("dcf.screener_form"))

    cookies_path = current_app.config["SCREENER_COOKIES_PATH"]
    upload_dir = current_app.config["UPLOAD_FOLDER"]

    try:
        downloaded_path = auto_download(
            company_symbol, cookies_path, upload_dir,
            use_consolidated=f.get("use_consolidated") == "on",
        )
    except ValuationError as e:
        flash(str(e), "danger")
        return redirect(url_for("dcf.screener_form"))
    except Exception:
        logger.exception("Unexpected error during Screener.in auto-download for %s", company_symbol)
        flash(
            "Auto-download hit an unexpected error. This feature hasn't been "
            "tested against the live site yet — please share the error details "
            "so it can be fixed.",
            "danger",
        )
        return redirect(url_for("dcf.screener_form"))

    # Auto-download only fetches the file — it does NOT run the valuation.
    # We hand the saved filename back to the normal form (as a hidden field)
    # so the user can set historical years, tax rate, terminal growth,
    # rf/rm, discount/margin overrides, peer tickers (auto-fetch or manual)
    # — every option the manual-upload path has — before clicking
    # "Run Valuation" themselves.
    flash(
        f"Downloaded {company_symbol}'s data from Screener.in. Set your "
        f"assumptions below, then click Run Valuation.",
        "success",
    )
    return render_template(
        "dcf/screener_form.html",
        prefilled_path=os.path.basename(downloaded_path),
        prefill_company_name=f.get("company_name", "").strip() or company_symbol,
        prefill_ticker=company_symbol,
    )


@bp.route("/dcf/screener", methods=["GET"])
@login_required
def screener_form():
    return render_template("dcf/screener_form.html")


@bp.route("/dcf/screener/analyze", methods=["POST"])
@login_required
def screener_analyze():
    f = request.form
    excel_file = request.files.get("excel_file")
    upload_dir = current_app.config["UPLOAD_FOLDER"]

    if excel_file and excel_file.filename != "":
        saved_name = f"{uuid.uuid4().hex}_{excel_file.filename}"
        saved_path = os.path.join(upload_dir, saved_name)
        excel_file.save(saved_path)
    else:
        # Fall back to a file fetched via "Auto-download from Screener.in" —
        # prefilled_path is just a basename (set by screener_auto_download),
        # so resolve it against upload_dir and confirm it's actually inside
        # that directory before trusting it.
        prefilled_name = os.path.basename((f.get("prefilled_path") or "").strip())
        candidate = os.path.join(upload_dir, prefilled_name) if prefilled_name else ""
        if prefilled_name and os.path.commonpath([os.path.abspath(candidate), os.path.abspath(upload_dir)]) == os.path.abspath(upload_dir) and os.path.isfile(candidate):
            saved_path = candidate
        else:
            flash("Please upload a Screener-format Excel file, or use Auto-download above.", "danger")
            return redirect(url_for("dcf.screener_form"))

    def num(name, default=0.0):
        try:
            return float(f.get(name, default) or default)
        except ValueError:
            return default

    def integer(name, default=0):
        try:
            return int(f.get(name, default) or default)
        except ValueError:
            return default

    peers = []
    for i in range(1, 6):  # up to 5 manual peers — see form notice re: dynamic add-row
        name = f.get(f"peer{i}_name", "").strip()
        pe = num(f"peer{i}_pe", 0)
        ev_ebitda = num(f"peer{i}_ev_ebitda", 0)
        if name and (pe > 0 or ev_ebitda > 0):
            peers.append({"name": name, "pe": pe, "ev_ebitda": ev_ebitda})

    def per_year_list(prefix):
        vals = [num(f"{prefix}_yr{i}", 0) for i in range(1, 16)]
        return vals if any(v > 0 for v in vals) else None

    params = {
        "company_name": f.get("company_name", "").strip(),
        "num_shares": integer("num_shares", 0),  # 0 = fall through to Excel/Yahoo/default chain
        "ticker": f.get("ticker", "").strip(),
        "exchange": f.get("exchange", "NS"),
        "tax_rate": num("tax_rate", 25.0),
        "terminal_growth": num("terminal_growth", 4.0),
        "historical_years": integer("historical_years", 0),
        "projection_years": integer("projection_years", 5),
        "manual_rf_rate": num("manual_rf_rate", 6.83),
        "manual_rm_rate": num("manual_rm_rate", 12.0),
        "manual_discount_rate": num("manual_discount_rate", 0),
        "run_dcf": f.get("run_dcf") == "on",
        "run_rim": f.get("run_rim") == "on",
        "run_comp": f.get("run_comp") == "on",
        # Advanced projection overrides — 0 means "auto" throughout
        "rev_growth_per_year": per_year_list("rev_growth"),
        "ebitda_margin_per_year": per_year_list("ebitda_margin"),
        "rev_growth_override": num("rev_growth_override", 0),
        "opex_margin_override": num("opex_margin_override", 0),
        "ebitda_margin_override": num("ebitda_margin_override", 0),
        "capex_ratio_override": num("capex_ratio_override", 0),
        "depreciation_rate_override": num("depreciation_rate_override", 0),
        "depreciation_method": f.get("depreciation_method", "Auto"),
        "inventory_days_override": num("inventory_days_override", 0),
        "debtor_days_override": num("debtor_days_override", 0),
        "creditor_days_override": num("creditor_days_override", 0),
        "interest_rate_override": num("interest_rate_override", 0),
        "working_capital_pct_override": num("working_capital_pct_override", 0),
        # RIM overrides
        "rim_required_return": num("rim_required_return", 0),
        "rim_assumed_roe": num("rim_assumed_roe", 0),
        "rim_terminal_growth": num("rim_terminal_growth", 0),
        "rim_projection_years": integer("rim_projection_years", 0),
        "peers": peers,
        "peer_tickers": f.get("peer_tickers", "").strip(),
    }

    try:
        result = run_screener_valuation(saved_path, params)
    except ValuationError as e:
        flash(str(e), "danger")
        return redirect(url_for("dcf.screener_form"))
    except Exception:
        logger.exception("Unexpected error running screener valuation")
        flash("Something went wrong while running the valuation. Check the Excel file and try again.", "danger")
        return redirect(url_for("dcf.screener_form"))
    finally:
        try:
            os.remove(saved_path)
        except OSError:
            pass

    result_id = uuid.uuid4().hex
    from app.dcf.history_service import save_history
    entry_id = save_history(current_user.id, "screener", result, params)
    cache.set(f"result:{result_id}", ("screener", result, params.get("company_name") or "Company", 0), timeout=900)

    if result.get("is_bank_valuation"):
        return render_template("dcf/bank_results.html", r=result, params=params, mode="screener", result_id=result_id, entry_id=entry_id)
    return render_template("dcf/screener_results.html", r=result, params=params, result_id=result_id, entry_id=entry_id)
