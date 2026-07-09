"""
Orchestrates "Screener Excel Mode (Screener.in Template)".

CORRECTED VERSION: an earlier port of this used screener_excel_handler.py
for parsing, which was NOT the module the original app's UI actually
imported (PHASE5_DCF_valuation.py imports from screener_excel_mode.py).
The wrong module didn't do the Crores->Lacs unit conversion Screener.in's
export needs, which silently produced fair values off by ~100x -- this
was very likely the "very rubbish valuation" bug. Now uses the correct
screener_excel_mode.py-derived engine (app/logic/screener_excel_engine.py)
throughout, including its own Screener-specific DDM/RIM math, matching
the original app exactly rather than reusing the generic DCF-engine DDM/RIM.

Shares outstanding priority (highest wins): manual override > extracted
from the Excel file's "No. of Equity Shares" row > Yahoo Finance (via an
optional ticker) > a hard 100-share fallback so the page never crashes.

WACC/beta FIX: the original app's Screener mode computes WACC beta from
`peer_tickers` via Hamada unlever/relever (calculate_wacc's own peer
branch) — exactly like Unlisted mode — NOT from the single "ticker"
field. That field's raw Yahoo beta is fetched only for the current-price
display; the original source even comments "beta not needed for Screener
mode" next to it. An earlier port here mistakenly overrode WACC's beta
with that single-ticker raw beta (skipping the peer unlever/relever
entirely, and silently defaulting the bank-mode branch's peer_tickers to
""), which produced a wrong cost of equity and therefore a wrong DCF
fair value. Now matches the original: peer_tickers drives beta for both
normal and bank-mode WACC, with beta_start_date/beta_end_date support
matching Listed mode.
"""
from app.dcf.errors import ValuationError
from app.dcf.unlisted_service import none_if_zero
from app.logic import dcf_engine as de
from app.logic import screener_excel_engine as se


def run_screener_valuation(excel_path: str, params: dict) -> dict:
    df_bs, df_pl = se.parse_screener_excel_to_dataframes(excel_path)
    if df_bs is None or df_pl is None or df_bs.empty or df_pl.empty:
        raise ValuationError(
            "Failed to parse the Screener Excel file. Make sure it matches "
            "the Screener_template.xlsx format (sheets 'Balance Sheet' and "
            "'Profit and Loss Account', with a 'Report Date' row of years)."
        )

    year_cols_all = se.detect_screener_year_columns(df_bs)
    if len(year_cols_all) < 2:
        raise ValuationError("Need at least 2 years of historical data in the Excel file.")

    historical_years = params["historical_years"]
    year_cols = year_cols_all[-historical_years:] if historical_years else year_cols_all

    financials = se.extract_screener_financials(df_bs, df_pl, year_cols)
    if financials is None:
        raise ValuationError("Failed to extract financial data — check the Excel file's line items match the template.")

    latest_year_col = year_cols[-1]  # extract_screener_financials reverses to newest-first; latest raw column is the last one passed in

    # --- shares outstanding: manual > (Yahoo if use_yahoo_shares checked,
    # else Excel) > (the other of Yahoo/Excel as fallback) > 100 fallback.
    # Mirrors the original app's explicit "Fetch shares outstanding from
    # Yahoo Finance" checkbox: unchecked (default) means Excel wins even
    # if a ticker is given; checked means Yahoo is tried first.
    shares_source = None
    shares = params.get("num_shares", 0)
    use_yahoo_shares = params.get("use_yahoo_shares", False)
    if shares and shares > 0:
        shares_source = "Manual override"
    elif not use_yahoo_shares:
        shares = se.get_screener_shares_outstanding(df_bs, latest_year_col)
        if shares > 0:
            shares_source = "Extracted from Excel (No. of Equity Shares)"

    current_price = 0.0
    beta = 1.0
    ticker_used = None
    ticker = params.get("ticker", "").strip()
    if ticker:
        yahoo_data = se.fetch_ticker_data_for_screener(ticker, params.get("exchange", "NS"))
        if not yahoo_data.get("error"):
            current_price = yahoo_data.get("current_price", 0.0)
            beta = yahoo_data.get("beta", 1.0)
            ticker_used = yahoo_data.get("ticker")
            if not shares_source and yahoo_data.get("shares"):
                shares = yahoo_data["shares"]
                shares_source = "Yahoo Finance"

    if not shares_source and use_yahoo_shares:
        # Yahoo was tried first (per checkbox) and didn't have shares —
        # fall back to Excel before giving up entirely.
        shares = se.get_screener_shares_outstanding(df_bs, latest_year_col)
        if shares > 0:
            shares_source = "Extracted from Excel (Yahoo Finance fallback)"

    if not shares_source:
        shares = 100
        shares_source = "Default fallback (100) — no manual value, Excel shares row, or ticker given"

    classification = de.classify_business_model(financials, income_stmt=None, balance_sheet=None)
    is_bank_like = de.show_classification_warning(classification)

    result = {
        "company_name": params.get("company_name") or "Screener Import",
        "csym": "₹",
        "shares": shares,
        "shares_source": shares_source,
        "current_price": current_price,
        "ticker": ticker_used,
        "classification": classification,
        "is_bank_like": is_bank_like,
        "financials": financials,
    }

    if is_bank_like:
        from app.dcf.bank_service import run_bank_valuation
        bank_params = {
            "tax_rate": params["tax_rate"],
            "terminal_growth": params["terminal_growth"],
            "projection_years": params["projection_years"],
            "manual_rf_rate": params["manual_rf_rate"],
            "manual_rm_rate": params["manual_rm_rate"],
            "peer_tickers": params.get("peer_tickers", ""),
            "car_ratio": params.get("car_ratio", 14.0),
            "rwa_percentage": params.get("rwa_percentage", 75.0),
        }
        bank_result = run_bank_valuation(financials, shares, bank_params)
        result.update(bank_result)
        result["is_bank_valuation"] = True
        return result

    wc_metrics = de.calculate_working_capital_metrics(financials)
    projections, drivers = de.project_financials(
        financials, wc_metrics, params["projection_years"], params["tax_rate"],
        none_if_zero(params["rev_growth_override"]),
        none_if_zero(params["opex_margin_override"]),
        capex_ratio_override=none_if_zero(params["capex_ratio_override"]),
        ebitda_margin_override=none_if_zero(params["ebitda_margin_override"]),
        depreciation_rate_override=none_if_zero(params["depreciation_rate_override"]),
        depreciation_method=params.get("depreciation_method", "Auto"),
        inventory_days_override=none_if_zero(params["inventory_days_override"]),
        debtor_days_override=none_if_zero(params["debtor_days_override"]),
        creditor_days_override=none_if_zero(params["creditor_days_override"]),
        interest_rate_override=none_if_zero(params["interest_rate_override"]),
        working_capital_pct_override=none_if_zero(params["working_capital_pct_override"]),
        rev_growth_per_year=params.get("rev_growth_per_year"),
        ebitda_margin_per_year=params.get("ebitda_margin_per_year"),
    )

    # Beta: the original app's Screener mode does NOT use the single ticker's
    # raw beta for WACC (that field is fetched only for the current-price
    # display — see its own comment "beta not needed for Screener mode").
    # WACC beta instead comes from peer_tickers via Hamada unlever/relever,
    # same as Unlisted mode. Falls back to 1.0 if no peers are given.
    peer_tickers_for_beta = params.get("peer_tickers", "").strip()
    wacc_details = de.calculate_wacc(
        financials, params["tax_rate"], peer_tickers=peer_tickers_for_beta or None,
        manual_rf_rate=params["manual_rf_rate"], manual_rm_rate=params["manual_rm_rate"],
        beta_start_date=params.get("beta_start_date"), beta_end_date=params.get("beta_end_date"),
    )

    cash_balance = financials["cash"][0] if financials["cash"][0] > 0 else 0
    manual_discount = params["manual_discount_rate"] if params["manual_discount_rate"] > 0 else None
    valuation = None
    if params.get("run_dcf", True):
        valuation, dcf_error = de.calculate_dcf_valuation(
            projections, wacc_details, params["terminal_growth"], shares, cash_balance,
            manual_discount_rate=manual_discount,
        )
        if dcf_error:
            raise ValuationError(dcf_error)

    # Screener-specific DDM/RIM (percentages -> decimals for these two calls only)
    rim_required_return = params.get("rim_required_return", 0)
    rim_required_return = (rim_required_return / 100) if rim_required_return > 0 else (wacc_details["ke"] / 100)
    rim_terminal_growth = params.get("rim_terminal_growth", 0)
    rim_terminal_growth = (rim_terminal_growth / 100) if rim_terminal_growth > 0 else (params["terminal_growth"] / 100)
    rim_projection_years = params.get("rim_projection_years", 0) or params["projection_years"]

    ddm_result = None
    if params.get("run_ddm", True):
        ddm_result = se.calculate_screener_ddm_valuation(
            financials, shares,
            required_return=rim_required_return,
            growth_rate=rim_terminal_growth,
        )
    rim_result = None
    if params.get("run_rim", True):
        rim_assumed_roe = params.get("rim_assumed_roe", 0)
        rim_assumed_roe = (rim_assumed_roe / 100) if rim_assumed_roe > 0 else None
        rim_result = se.calculate_screener_rim_valuation(
            financials, shares,
            required_return=rim_required_return,
            projection_years=rim_projection_years,
            terminal_growth=rim_terminal_growth,
            assumed_roe=rim_assumed_roe,
        )

    manual_peer_valuation = None
    if params.get("peers"):
        manual_peer_valuation = se.calculate_manual_peer_valuation(financials, shares, params["peers"])

    # Ticker-based peer comparables (P/E, P/B, P/S, EV/EBITDA, EV/Sales) — same
    # engine the Listed mode uses. target_ticker=None routes perform_comparative_valuation
    # into its "unlisted-style" branch, which uses target_financials/target_shares
    # directly instead of trying to look the company itself up on Yahoo Finance.
    comp_results = None
    peer_tickers = params.get("peer_tickers", "").strip()
    if params.get("run_comp", True) and peer_tickers:
        try:
            comp_results = de.perform_comparative_valuation(
                None, peer_tickers, financials, shares,
                params.get("exchange", "NS"), projections=projections,
            )
        except Exception:
            comp_results = None  # relative valuation is a bonus, not core — fail soft

    charts = {
        "historical": de.create_historical_financials_chart(financials),
        "projections": de.create_fcff_projection_chart(projections),
        "wacc_breakdown": de.create_wacc_breakdown_chart(wacc_details),
    }
    if valuation:
        charts["waterfall"] = de.create_waterfall_chart(valuation)

    result.update({
        "wacc_details": wacc_details,
        "wc_metrics": wc_metrics,
        "projections": projections,
        "drivers": drivers,
        "valuation": valuation,
        "ddm_result": ddm_result,
        "rim_result": rim_result,
        "manual_peer_valuation": manual_peer_valuation,
        "comp_results": comp_results,
        "charts": {k: (de.apply_chart_theme(v).to_json() if v is not None else None) for k, v in charts.items()},
        "tax_rate": params["tax_rate"],
        "terminal_growth": params["terminal_growth"],
    })
    return result
