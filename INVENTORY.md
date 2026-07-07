# Phase 0 — Inventory (Streamlit → Flask migration)

## 1. File classification

### Pure logic — copy unchanged into `app/logic/`
No `st.*` calls at all. Safe to import directly, zero rewrite needed.
- `pdf_exporter.py`
- `pdf_generator_comprehensive.py`
- `screener_downloader.py`
- `ticker_cache_utils.py`
- `utils_indian_apis.py`
- `utils_peer_fetcher.py`
- `screener_data_parser.py` (3 stray `st.*` calls — see §3)

### UI-coupled — need route + template rewrite
Contain real Streamlit UI (forms, charts, session_state reads).
- `PHASE5_DCF_valuation.py` — the monolith. Lines 1–5793 are calculation
  functions (DCF, WACC, RIM, DDM, relative valuation, chart builders).
  Line 5794 (`def main()`) to EOF (12150) is 100% UI — this is what gets
  rewritten as Flask routes/templates, phase by phase.
- `screener_excel_mode.py`, `screener_auto_download_streamlit.py`,
  `screener_excel_handler.py`, `peer_comparison_charts.py`,
  `peer_metrics_enhanced.py`, `dcf_screener_integration.py`,
  `stock_price_comparison.py`, `proxy_fetcher.py`, `yf_ratelimit.py`
  — mix of logic + `st.*` display calls. Logic parts get extracted,
  display parts get rewritten as templates in Phases 3–5.

### Data/assets — copy as-is
- `Screener_template.xlsx`, `RELIANCE_template.xlsx`, `screener_cookies.pkl`,
  `peer_cache.json`

## 2. App structure discovered (drives routing design)

Single page, one radio button = three modes:
- **Listed Company (Yahoo Finance)** → will become `/dcf/listed`
- **Unlisted Company (Excel Upload)** → will become `/dcf/unlisted`
- **Screener Excel Mode** → will become `/dcf/screener`

Each mode has its own tab set for results (`st.tabs(...)` at lines 7154,
8003, 10036, 11509) → each becomes its own template partial
(`_tab_summary.html`, `_tab_wacc.html`, etc.) included into one results
page per mode.

## 3. `st.session_state` key inventory → where it goes now

| Old key pattern (suffix `_listed`/`_unlisted`/`_screener`) | New home |
|---|---|
| `show_results_*`, `previous_inputs_*` | Form re-population: read back from the submitted form / a per-analysis DB row, not global session |
| `cached_rf_rate_*`, `cached_rm_rate_*`, `manual_rf_*`, `manual_rm_*`, `rf_fetch_*`, `rm_fetch_*` | Server-side cache (Flask-Caching) keyed by ticker, not per-user session |
| `bse_peers_*`, `nse_peers_*`, `worldwide_peers_*` | Submitted form field (comma-separated peers input), passed straight to the calc functions — no need to persist |
| `current_ticker`, `company_symbol`, `data_type`, `fetch_status` | Request-scoped (Flask `g` or just local variables in the route), not session |
| `yahoo_request_count`, `last_yahoo_request`, `session_start_time` | Global in-process rate limiter (module-level object in `yf_ratelimit.py`), shared across all users — matches actual intent (protecting the Yahoo API key, not per-user) |
| `auto_downloaded_file`, `pdf_bytes` | Temp file on disk / in-memory bytes returned directly as the HTTP response, not stored in session |
| `bank_params_applied`, `rf_rate_initialized` | One-time init flags — become defaults baked into the form, not stateful flags |

**Net effect:** almost nothing needs Flask's `session` object. Most
"session state" in the old app was actually either (a) form state that
belongs in the request, or (b) a shared cache that belongs on the server,
not per-user. This simplifies the port a lot.

## 4. Stray `st.*` calls inside logic functions (need small edits, not rewrites)

Found in the calculation section (lines 1–5793) of `PHASE5_DCF_valuation.py`
and in `screener_data_parser.py`:
- `st.cache_data(ttl=3600)` decorator → replace with `flask_caching`'s
  `@cache.memoize(timeout=3600)`
- `st.success` / `st.info` / `st.warning` / `st.write` calls sprinkled in
  calc functions (e.g. WACC/FCFF adjustment notes) → convert to a
  `messages: list[str]` return value that templates render as alert boxes,
  instead of a side-effecting UI call
- `st.error(traceback.format_exc())` → standard Python logging
- Rate-limit session_state block at top of file → moves into
  `yf_ratelimit.py` as a module-level limiter (already partially there)

## 5. Dependencies to drop from `requirements.txt`

Confirmed unused anywhere in the codebase:
- `streamlit`, `streamlit-aggrid` (obviously)
- `nsepy` (grep found zero imports)

Everything else (pandas, yfinance, plotly, reportlab, python-docx,
python-pptx, openpyxl, xlsxwriter, sqlalchemy, etc.) stays — it's the
business logic, not the UI framework.

## 6. Migration order (maps to Phases 2–5 of the plan)

1. Auth + skeleton (Phase 1 — this delivery)
2. Listed Company mode — most-used path, good first full vertical slice
3. Charts (Plotly.js) + tables — needed by every mode, build once, reuse
4. File upload/download (Excel/PDF) — needed by Unlisted + Screener modes
5. Unlisted Company mode
6. Screener Excel mode + peer comparison + auto-download
7. Parity checklist against the old app
