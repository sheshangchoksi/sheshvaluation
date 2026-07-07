"""
Auto-download from Screener.in: uses a server-side saved login session
(cookies file) to fetch a company's Excel export directly and convert
it to the standard template format.

SIMPLIFIED from an earlier version: the converted file
(ScreenerDownloader.auto_download_and_convert) uses sheet names
"Balance Sheet"/"Profit and Loss Account" -- which is exactly what
screener_excel_engine.py (the CORRECT parser, see screener_service.py's
docstring) expects natively. An earlier version of this file wrote a
separate parser to bridge a sheet-naming mismatch that turned out to
only exist because a different, wrong parsing module was being used
elsewhere -- now that that's fixed, auto-download and manual upload both
flow through the exact same parsing + valuation pipeline. One pipeline,
not two.

Still true: this was NOT tested against the live Screener.in site from
this environment (no network access here) -- the download step itself
needs your first real test run.
"""
import os

from app.dcf.errors import ValuationError
from app.logic.screener_downloader import ScreenerDownloader


def _is_auth_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(kw in text for kw in ("login", "authentic", "cookie", "session", "403", "401"))


def auto_download(company_symbol: str, cookies_path: str, output_dir: str, use_consolidated: bool = False) -> str:
    """Returns the path to the downloaded, template-formatted Excel file
    (ready to pass straight to screener_service.run_screener_valuation).
    Raises ValuationError with a clear message for expected failure modes."""
    if not os.path.exists(cookies_path):
        raise ValuationError(
            f"Screener.in cookies file not found at {cookies_path}. "
            "This feature needs a saved login session — see the setup note on the form."
        )

    try:
        downloader = ScreenerDownloader(cookies_path)
        template_path = downloader.auto_download_and_convert(
            company_symbol, output_dir=output_dir, use_consolidated=use_consolidated
        )
    except Exception as e:
        if _is_auth_error(e):
            raise ValuationError(
                "Screener.in login session appears to be expired or invalid. "
                "The saved cookies need to be refreshed."
            )
        raise ValuationError(f"Auto-download failed: {e}")

    if not template_path or not os.path.exists(template_path):
        raise ValuationError(
            f"Could not download data for '{company_symbol}' from Screener.in. "
            "Check the symbol is correct, or the site's page structure may have "
            "changed since this feature was built."
        )

    return template_path
