"""
Bank/NBFC-specific valuation — ported from the old app's bank branch.
Banks can't use standard FCFF/WACC (debt is raw material, not financing),
so this uses: FCFE discounted at Ke, plus RIM, DDM, and P/B-ROE as
cross-checks — exactly the four methods the old app ran for banks.
"""
from app.dcf.errors import ValuationError
from app.logic import dcf_engine as de


def run_bank_valuation(financials: dict, shares: int, params: dict) -> dict:
    """
    params keys: tax_rate, terminal_growth, projection_years,
    manual_rf_rate, manual_rm_rate, peer_tickers (comma-separated,
    optional — used for Hamada unlever/relever beta), car_ratio,
    rwa_percentage, beta_start_date, beta_end_date (optional)
    """
    wacc_details = de.calculate_wacc_bank(
        financials, params["tax_rate"],
        peer_tickers=params.get("peer_tickers") or None,
        manual_rf_rate=params["manual_rf_rate"],
        manual_rm_rate=params["manual_rm_rate"],
        beta_start_date=params.get("beta_start_date"),
        beta_end_date=params.get("beta_end_date"),
    )

    projections, drivers = de.project_financials_bank(
        financials, params["projection_years"], params["tax_rate"],
        car_ratio=params.get("car_ratio", 14.0),
        rwa_percentage=params.get("rwa_percentage", 75.0),
    )
    if projections is None:
        raise ValuationError("Insufficient data to project bank financials (need revenue, NOPAT, and equity history).")

    projections["roe"] = drivers["roe"]  # calculate_bank_fcfe_valuation reads this for sustainable growth

    fcfe_valuation, fcfe_error = de.calculate_bank_fcfe_valuation(
        projections, wacc_details["ke"], params["terminal_growth"], shares
    )
    if fcfe_error:
        raise ValuationError(fcfe_error)

    rim_result = de.calculate_residual_income_model(
        financials, shares, wacc_details["ke"],
        terminal_growth=params["terminal_growth"],
        projection_years=params["projection_years"],
    )

    ddm_result = de.calculate_dividend_discount_model(
        financials, shares, wacc_details["ke"]
    )

    pb_roe_result = de.calculate_pb_roe_valuation(
        financials, shares, wacc_details["ke"]
    )

    charts = {
        "historical": de.create_historical_financials_chart(financials),
    }
    comparison_chart = None
    try:
        vals_for_chart = {
            "Bank FCFE": fcfe_valuation["fair_value_per_share"],
            "RIM": rim_result.get("value_per_share", 0) if rim_result else 0,
            "DDM": ddm_result.get("value_per_share", 0) if ddm_result else 0,
            "P/B-ROE": pb_roe_result.get("value_per_share", 0) if pb_roe_result else 0,
        }
        comparison_chart = de.create_bank_valuation_comparison_chart(vals_for_chart)
    except Exception:
        comparison_chart = None
    if comparison_chart is not None:
        charts["comparison"] = comparison_chart

    return {
        "wacc_details": wacc_details,
        "projections": projections,
        "drivers": drivers,
        "fcfe_valuation": fcfe_valuation,
        "rim_result": rim_result,
        "ddm_result": ddm_result,
        "pb_roe_result": pb_roe_result,
        "charts": {k: (de.apply_chart_theme(v).to_json() if v is not None else None) for k, v in charts.items()},
    }
