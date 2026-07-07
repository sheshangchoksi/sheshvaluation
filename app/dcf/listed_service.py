"""
Orchestrates the "Listed Company (Yahoo Finance)" valuation workflow.
This is the Flask replacement for the `mode == "Listed Company"` branch
of the old app's main(). Scope for Phase 2 (see INVENTORY.md for what's
deferred to later phases):

INCLUDED:
- Ticker/exchange input, historical & projection years, tax rate,
  terminal growth, manual Rf/Rm, optional manual discount rate override
- Business model classification (bank/NBFC detection)
- Standard FCFF DCF, WACC breakdown, DDM, RIM
- Optional relative (peer) valuation if peer tickers are supplied
- Historical financials, projections, WACC, sensitivity charts

DEFERRED (placeholders / not wired up yet):
- Bank/NBFC-specific valuation branch (RIM/DDM/P-B-ROE/Bank-FCFE) —
  currently just shows a notice instead of running
- Screener.in as an alternate data source toggle
- Auto-fetch peers button, peer comparison 3D dashboard
- Stock price vs financials comparison tab
- Automatic PDF export
- Advanced per-year projection overrides (revenue growth/EBITDA margin
  per year, capex/depreciation/working-capital overrides)
"""
import numpy as np

from app.dcf.errors import ValuationError
from app.logic import dcf_engine as de


EXCHANGE_MAP = {
    "NSE": ("NS", True),
    "BSE": ("BO", True),
    "NASDAQ/NYSE": ("", False),
    "LSE": ("L", False),
    "SSE/HKEX": ("", False),
    "Other": ("", False),
}

DEFAULT_RF = {"NSE": 6.83, "BSE": 6.83, "NASDAQ/NYSE": 4.25, "LSE": 4.10, "SSE/HKEX": 2.50, "Other": 4.50}
DEFAULT_RM = {"NSE": 12.0, "BSE": 12.0, "NASDAQ/NYSE": 10.5, "LSE": 9.5, "SSE/HKEX": 9.0, "Other": 10.0}


def defaults_for_exchange(exchange):
    return {
        "rf": DEFAULT_RF.get(exchange, 6.83),
        "rm": DEFAULT_RM.get(exchange, 12.0),
    }


def none_if_zero(v):
    return None if (v is None or v == 0) else v


def run_listed_valuation(params: dict) -> dict:
    """
    params keys (all already validated/typed by the route):
      ticker, exchange, historical_years, projection_years, tax_rate,
      terminal_growth, manual_rf_rate, manual_rm_rate,
      manual_discount_rate (0 = auto), manual_shares_override (0 = auto),
      peer_tickers (comma-separated string, may be empty),
      beta_start_date, beta_end_date (date objects or None),
      rev_growth_override, opex_margin_override, ebitda_margin_override,
      capex_ratio_override, depreciation_rate_override, depreciation_method,
      inventory_days_override, debtor_days_override, creditor_days_override,
      interest_rate_override, working_capital_pct_override (0 = auto)

    Returns a dict the results template renders. Raises ValuationError
    for expected failure modes (old app used st.error + st.stop() for
    these — here we raise and the route turns it into a flashed error).
    """
    ticker = params["ticker"].strip()
    exchange = params["exchange"]
    exchange_suffix, is_indian_exchange = EXCHANGE_MAP.get(exchange, ("", False))

    yahoo_data, error = de.fetch_yahoo_financials(ticker, exchange_suffix)
    if error:
        raise ValuationError(error)

    shares = yahoo_data.get("shares", 0)
    shares_source = yahoo_data.get("shares_source", "Unknown")
    company_name = yahoo_data["info"].get("longName", ticker)
    yahoo_data["_data_source"] = "yahoo"
    csym = de.get_currency_symbol(yahoo_data.get("info"))
    current_price = (
        yahoo_data["info"].get("currentPrice", 0)
        or yahoo_data["info"].get("regularMarketPrice", 0)
        or 0
    )

    if params.get("manual_shares_override", 0) > 0:
        shares = params["manual_shares_override"]
        shares_source = "Manual Override (User Input)"
    elif shares == 0:
        info = yahoo_data.get("info", {})
        market_cap = info.get("marketCap", 0)
        if market_cap > 0 and current_price > 0:
            shares = int(market_cap / current_price)
            shares_source = "Calculated (Market Cap ÷ Current Price)"
        else:
            raise ValuationError(
                "Could not determine shares outstanding for this ticker. "
                "Try again with a manual shares override."
            )

    financials = de.extract_financials_listed(yahoo_data, num_years=params["historical_years"])
    if financials is None:
        raise ValuationError("Failed to extract financial data for this ticker.")

    classification = de.classify_business_model(
        financials,
        income_stmt=yahoo_data["income_statement"],
        balance_sheet=yahoo_data["balance_sheet"],
    )
    is_bank_like = de.show_classification_warning(classification)

    result = {
        "ticker": ticker,
        "exchange": exchange,
        "company_name": company_name,
        "csym": csym,
        "shares": shares,
        "shares_source": shares_source,
        "current_price": current_price,
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
            "beta_start_date": params.get("beta_start_date"),
            "beta_end_date": params.get("beta_end_date"),
        }
        bank_result = run_bank_valuation(financials, shares, bank_params)
        result.update(bank_result)
        result["is_bank_valuation"] = True
        return result

    full_ticker = de.get_ticker_with_exchange(ticker, exchange_suffix)
    beta_start = params.get("beta_start_date")
    beta_end = params.get("beta_end_date")
    beta = de.get_stock_beta(full_ticker, period_years=3, beta_start_date=beta_start, beta_end_date=beta_end)

    wacc_details = de.calculate_wacc(
        financials,
        params["tax_rate"],
        peer_tickers=None,
        manual_rf_rate=params["manual_rf_rate"],
        manual_rm_rate=params["manual_rm_rate"],
        beta_start_date=beta_start,
        beta_end_date=beta_end,
    )
    wacc_details["beta"] = beta
    wacc_details["ke"] = wacc_details["rf"] + (beta * (wacc_details["rm"] - wacc_details["rf"]))
    wacc_details["wacc"] = (
        (wacc_details["we"] / 100 * wacc_details["ke"])
        + (wacc_details["wd"] / 100 * wacc_details["kd_after_tax"])
    )

    wc_metrics = de.calculate_working_capital_metrics(financials)
    projections, drivers = de.project_financials(
        financials, wc_metrics, params["projection_years"], params["tax_rate"],
        none_if_zero(params.get("rev_growth_override", 0)),
        none_if_zero(params.get("opex_margin_override", 0)),
        capex_ratio_override=none_if_zero(params.get("capex_ratio_override", 0)),
        ebitda_margin_override=none_if_zero(params.get("ebitda_margin_override", 0)),
        depreciation_rate_override=none_if_zero(params.get("depreciation_rate_override", 0)),
        depreciation_method=params.get("depreciation_method", "Auto"),
        inventory_days_override=none_if_zero(params.get("inventory_days_override", 0)),
        debtor_days_override=none_if_zero(params.get("debtor_days_override", 0)),
        creditor_days_override=none_if_zero(params.get("creditor_days_override", 0)),
        interest_rate_override=none_if_zero(params.get("interest_rate_override", 0)),
        working_capital_pct_override=none_if_zero(params.get("working_capital_pct_override", 0)),
    )

    cash_balance = financials["cash"][0] if financials["cash"][0] > 0 else 0
    manual_discount = params["manual_discount_rate"] if params["manual_discount_rate"] > 0 else None
    valuation, dcf_error = de.calculate_dcf_valuation(
        projections, wacc_details, params["terminal_growth"], shares, cash_balance,
        manual_discount_rate=manual_discount,
    )
    if dcf_error:
        raise ValuationError(dcf_error)

    ddm_result = de.calculate_dividend_discount_model(
        financials, shares, wacc_details["ke"], ticker=ticker, dcf_projections=projections
    )
    rim_result = de.calculate_residual_income_model(
        financials, shares, wacc_details["ke"],
        terminal_growth=params["terminal_growth"],
        projection_years=params["projection_years"],
        dcf_projections=projections,
    )

    comp_results = None
    peer_tickers = params.get("peer_tickers", "").strip()
    if peer_tickers:
        try:
            comp_results = de.perform_comparative_valuation(
                ticker, peer_tickers, financials, shares, exchange_suffix, projections=projections
            )
        except Exception:
            comp_results = None  # relative valuation is a bonus, not core — fail soft

    wacc_range = np.arange(max(1.0, wacc_details["wacc"] - 3), wacc_details["wacc"] + 3.5, 0.5)
    g_range = np.arange(
        max(1.0, params["terminal_growth"] - 2),
        min(params["terminal_growth"] + 3, wacc_details["wacc"] - 1),
        0.5,
    )
    if len(g_range) == 0:
        g_range = np.array([params["terminal_growth"]])

    charts = {
        "price_vs_value": de.create_price_vs_value_gauge(current_price, valuation["fair_value_per_share"])
        if valuation["fair_value_per_share"] > 0 else None,
        "historical": de.create_historical_financials_chart(financials),
        "projections": de.create_fcff_projection_chart(projections),
        "wacc_breakdown": de.create_wacc_breakdown_chart(wacc_details),
        "waterfall": de.create_waterfall_chart(valuation),
        "sensitivity": de.create_sensitivity_heatmap(projections, wacc_range, g_range, shares),
    }

    result.update({
        "wacc_details": wacc_details,
        "wc_metrics": wc_metrics,
        "projections": projections,
        "drivers": drivers,
        "valuation": valuation,
        "ddm_result": ddm_result,
        "rim_result": rim_result,
        "comp_results": comp_results,
        "charts": {k: (de.apply_chart_theme(v).to_json() if v is not None else None) for k, v in charts.items()},
        "tax_rate": params["tax_rate"],
        "terminal_growth": params["terminal_growth"],
        "projection_years": params["projection_years"],
    })
    return result
