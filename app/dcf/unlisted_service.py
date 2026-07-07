"""
Orchestrates the "Unlisted Company (Excel Upload)" valuation workflow —
Flask replacement for the `mode == "Unlisted Company (Excel Upload)"`
branch of the old app's main(). Unlike Listed mode this one exposes the
full "Advanced Projection Assumptions" and "RIM Parameters" controls,
since those were explicitly asked for.

INCLUDED: Excel upload/parsing, business model classification, manual
Rf/Rm (with optional auto-fetch from a Yahoo ticker), beta date range,
full projection overrides (revenue growth, opex/EBITDA margin, capex,
depreciation method+rate, working capital days, interest rate),
RIM parameter overrides, optional relative valuation, toggle-able
DCF/RIM/Comparative sections.

DEFERRED: per-year (year-by-year) grid of growth/margin overrides — the
old app let you set Year 1..N individually via a dynamic form grid;
here only the single "applies to all years" override is wired up. Flag
if you want this added; it's a frontend (dynamic form fields) task more
than a backend one.
"""
from app.dcf.errors import ValuationError
from app.logic import dcf_engine as de


def none_if_zero(v):
    return None if (v is None or v == 0) else v


def run_unlisted_valuation(excel_path: str, params: dict) -> dict:
    df_bs, df_pl = de.parse_excel_to_dataframes(excel_path)
    if df_bs is None or df_pl is None:
        raise ValuationError("Failed to parse the Excel file. Make sure it matches the template's sheet names (BalanceSheet, Profit&Loss).")

    year_cols_all = de.detect_year_columns(df_bs)
    if len(year_cols_all) < 2:
        raise ValuationError("Need at least 2 years of historical data in the Excel file.")

    historical_years = params["historical_years"]
    if historical_years > len(year_cols_all):
        year_cols = year_cols_all
    else:
        year_cols = year_cols_all[-historical_years:]

    financials = de.extract_financials_unlisted(df_bs, df_pl, year_cols)
    if financials is None:
        raise ValuationError("Failed to extract financial data — check the Excel file's line items match the template.")

    classification = de.classify_business_model(financials, income_stmt=None, balance_sheet=None)
    is_bank_like = de.show_classification_warning(classification)

    shares = params["num_shares"]
    csym = "₹"  # Unlisted companies in this app are Indian entities (G-Sec Rf default, INR template)

    result = {
        "company_name": params.get("company_name") or "Unlisted Company",
        "csym": csym,
        "shares": shares,
        "classification": classification,
        "is_bank_like": is_bank_like,
        "financials": financials,
        "years_used": year_cols,
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
    )

    wacc_details = None
    manual_discount = params["manual_discount_rate"] if params["manual_discount_rate"] > 0 else None

    if params.get("run_dcf", True) or params.get("run_rim", True):
        wacc_details = de.calculate_wacc(
            financials, params["tax_rate"], peer_tickers=None,
            manual_rf_rate=params["manual_rf_rate"], manual_rm_rate=params["manual_rm_rate"],
        )
        # Unlisted companies have no market-observable beta — old app defaults to 1.0
        # unless peers are supplied for a proxy beta.
        beta = 1.0
        peer_tickers = params.get("peer_tickers", "").strip()
        if peer_tickers:
            try:
                beta = de.calculate_peer_unlevered_beta(peer_tickers, financials, params["tax_rate"])
            except Exception:
                beta = 1.0
        wacc_details["beta"] = beta
        wacc_details["ke"] = wacc_details["rf"] + (beta * (wacc_details["rm"] - wacc_details["rf"]))
        wacc_details["wacc"] = (
            (wacc_details["we"] / 100 * wacc_details["ke"])
            + (wacc_details["wd"] / 100 * wacc_details["kd_after_tax"])
        )

    valuation = None
    if params.get("run_dcf", True):
        cash_balance = financials["cash"][0] if financials["cash"][0] > 0 else 0
        valuation, dcf_error = de.calculate_dcf_valuation(
            projections, wacc_details, params["terminal_growth"], shares, cash_balance,
            manual_discount_rate=manual_discount,
        )
        if dcf_error:
            raise ValuationError(dcf_error)

    rim_result = None
    if params.get("run_rim", True):
        rim_required_return = params["rim_required_return"] if params["rim_required_return"] > 0 else wacc_details["ke"]
        rim_result = de.calculate_residual_income_model(
            financials, shares, rim_required_return,
            terminal_growth=params["rim_terminal_growth"] if params["rim_terminal_growth"] > 0 else params["terminal_growth"],
            projection_years=params["rim_projection_years"] if params["rim_projection_years"] > 0 else params["projection_years"],
            assumed_roe=none_if_zero(params["rim_assumed_roe"]),
            dcf_projections=projections,
        )

    comp_results = None
    peer_tickers = params.get("peer_tickers", "").strip()
    if params.get("run_comp", True) and peer_tickers:
        try:
            comp_results = de.perform_comparative_valuation(
                params.get("company_name", "Company"), peer_tickers, financials, shares, "NS", projections=projections
            )
        except Exception:
            comp_results = None

    charts = {
        "historical": de.create_historical_financials_chart(financials),
        "projections": de.create_fcff_projection_chart(projections),
    }
    if wacc_details:
        charts["wacc_breakdown"] = de.create_wacc_breakdown_chart(wacc_details)
    if valuation:
        charts["waterfall"] = de.create_waterfall_chart(valuation)

    result.update({
        "wacc_details": wacc_details,
        "wc_metrics": wc_metrics,
        "projections": projections,
        "drivers": drivers,
        "valuation": valuation,
        "rim_result": rim_result,
        "comp_results": comp_results,
        "charts": {k: (v.to_json() if v is not None else None) for k, v in charts.items()},
        "tax_rate": params["tax_rate"],
        "terminal_growth": params["terminal_growth"],
        "projection_years": params["projection_years"],
    })
    return result
