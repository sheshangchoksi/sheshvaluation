"""
Wires up PDF export using the professional PDF generator that was
already sitting inside the old app's calc region (generate_professional_pdf
/ export_to_pdf in dcf_engine.py) — nothing needed porting from
pdf_exporter.py/pdf_generator_comprehensive.py, those turned out to be
unused alternates.

Known limitation: the peer-comparison page inside the PDF generator
expects a different comp_results/peer_data shape than what
perform_comparative_valuation returns elsewhere in this app. Rather than
risk feeding it mismatched data, we pass an empty peer_data DataFrame,
which cleanly skips that page. Fair value bar chart, financials
overview, and DCF summary all work with real data.
"""
import os
import tempfile

import pandas as pd

from app.logic import dcf_engine as de


def build_pdf(result: dict, name: str, current_price: float = 0) -> str:
    """Returns the path to a generated PDF file (caller is responsible
    for cleanup after sending it)."""
    valuation = result.get("valuation") or {}
    wacc_details = result.get("wacc_details") or {}

    fair_values = {"DCF (FCFF)": valuation.get("fair_value_per_share", 0)}
    ddm = result.get("ddm_result")
    if ddm and ddm.get("value_per_share", 0) > 0:
        fair_values["DDM"] = ddm["value_per_share"]
    rim = result.get("rim_result")
    if rim and rim.get("value_per_share", 0) > 0:
        fair_values["RIM"] = rim["value_per_share"]

    dcf_results = {
        "fair_value_per_share": valuation.get("fair_value_per_share", 0),
        "wacc": (wacc_details.get("wacc", 0) or 0) / 100,          # PDF generator expects a decimal
        "terminal_growth_rate": (result.get("terminal_growth", 0) or 0) / 100,
        "forecast_years": result.get("projection_years", 5),
        "tax_rate": (result.get("tax_rate", 0) or 0) / 100,
        "enterprise_value": valuation.get("enterprise_value", 0),
        "net_debt": valuation.get("net_debt", 0),
        "equity_value": valuation.get("equity_value", 0),
        "shares": result.get("shares", 0),
    }

    data_package = {
        "company_name": result.get("company_name", name),
        "ticker": name,
        "current_price": current_price,
        "financials": result.get("financials", {}),
        "dcf_results": dcf_results,
        "fair_values": fair_values,
        "peer_data": pd.DataFrame(),   # see module docstring — comp_results shape mismatch avoided
        "comp_results": None,
    }

    temp_dir = tempfile.gettempdir()
    safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or "Report"
    output_path = os.path.join(temp_dir, f"{safe_name}_Valuation_Report.pdf")
    return de.generate_professional_pdf(data_package, output_path=output_path)
