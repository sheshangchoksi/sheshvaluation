# Parity Audit — Flask app vs. original Streamlit app

Last updated: after Phase 6 (partial) + Phase 5 audit. This is the
honest map — if it's not marked ✅ Done, don't assume it works.

## Listed Company mode

| Feature | Status |
|---|---|
| Ticker/exchange input, fetch from Yahoo Finance | ✅ Done |
| Historical/projection years | ✅ Done |
| Tax rate, terminal growth | ✅ Done |
| Manual Rf/Rm entry | ✅ Done |
| Manual discount rate / shares override | ✅ Done |
| Business model classification (bank/NBFC detection) | ✅ Done |
| WACC, FCFF DCF, DDM, RIM | ✅ Done |
| Beta calculation date range picker | ✅ Done (Phase 2B) |
| Auto-fetch peers button | ✅ Done (Phase 2B) — depends on Yahoo's "similar companies" endpoint, which is less reliable than a curated peer list; treat results as a starting point |
| Advanced projection overrides (growth, margins, capex, depreciation, working capital days, interest rate) | ✅ Done (Phase 2B) — single value applied to all years |
| Per-year (Year 1, Year 2, ...) individual overrides | ❌ Not built |
| Bank/NBFC-specific valuation branch (RIM/DDM/P-B-ROE/Bank FCFE) | ✅ Done (Phase 6) |
| Screener.in as an alternate data source toggle | ❌ Not built |
| Stock price vs. financials comparison chart | 🚫 Explicitly out of scope (your call) |
| Automatic PDF export | ✅ Done (Phase 6) |
| 3D peer comparison dashboard | ❌ Not built |

## Unlisted Company mode

| Feature | Status |
|---|---|
| Excel template download/upload | ✅ Done |
| Business model classification | ✅ Done |
| WACC (with Rf/Rm auto-fetch-from-ticker) | ✅ Done |
| FCFF DCF | ✅ Done |
| Advanced projection overrides (full set) | ✅ Done |
| RIM with its own parameter overrides | ✅ Done |
| Relative valuation (peer tickers) | ✅ Done |
| Auto-fetch peers | ✅ Done — via a reference ticker (a similar listed company), since an unlisted company has no ticker of its own to seed discovery from |
| Per-year individual overrides | ❌ Not built |
| Bank/NBFC-specific valuation branch | ✅ Done (Phase 6) |
| Automatic PDF export | ✅ Done (Phase 6) |

## Screener Excel Mode

| Feature | Status |
|---|---|
| Screener template download | ✅ Done |
| Excel upload & parsing (Screener.in export format) | ✅ Done — **found and fixed a real bug** in the original app's parser (`row.iloc[col]` used with a string column label, silently zeroing every value) |
| Business model classification | ✅ Done |
| WACC, FCFF DCF, RIM | ✅ Done |
| Manual peer comparison (P/E, EV/EBITDA) | ✅ Done — fixed number of peer slots (5) instead of a dynamically-added list |
| Revenue growth / opex margin override | ✅ Done (basic pair only, not the full Unlisted-style panel) |
| Auto-download from Screener.in (scraping with saved login cookies) | ❌ Not built — see note below |
| Bank/NBFC-specific valuation branch | ✅ Done (Phase 6) — same shared branch as Listed/Unlisted |
| Automatic PDF export | ✅ Done (Phase 6) |

## Cross-cutting features (apply to any/all modes)

| Feature | Status |
|---|---|
| Login (few known users) | ✅ Done |
| PDF export of results | ✅ Done for Listed/Unlisted/Screener (Phase 6). ❌ Not done for Bank/NBFC results — the bank result shape doesn't match the PDF generator's expected `dcf_results`/`fair_values` keys yet. Needs Chrome/Chromium on the server for embedded charts (Dockerfile installs it); without it, PDF still generates, just tables-only. |
| Peer-comparison page inside the PDF | ❌ Not wired — the PDF generator expects a different `comp_results`/`peer_data` shape than `perform_comparative_valuation` produces elsewhere. Passed as empty to avoid feeding it mismatched data; rest of the PDF (financials, DCF summary, fair-value chart) is unaffected. |
| Bank/NBFC-specific valuation branch | ✅ Done (Phase 6) for both Listed and Unlisted modes — FCFE DCF, RIM, DDM, P/B-ROE, cost-of-funds WACC |
| Stock price vs. financials comparison tab | 🚫 Explicitly out of scope (your call) — not building this |
| 3D peer comparison dashboard (`peer_comparison_charts.py`, `peer_metrics_enhanced.py`) | ❌ Not built |
| Auto-download financials directly from Screener.in using saved session cookies (`screener_downloader.py`, `screener_auto_download_streamlit.py`) | ✅ Built (Phase 5) — **untested against the live site**, see note below |
| Sensitivity heatmap | ✅ Done for Listed mode only |
| Deployment (Docker/Render/etc) | Dockerfile ready (now installs Chromium for PDF charts); not yet deployed anywhere (Phase 7) |

### Screener.in auto-download — built, but needs your first live test

It's wired up now (form on Screener Excel Mode page, "⚡ Auto-download"
section). What I fixed along the way, found by actually testing:

- The original app's own two modules disagreed with each other:
  `screener_downloader.py` writes sheets named "Balance Sheet" /
  "Profit and Loss Account" with granular Screener.in field names
  (`Net Block`, `Equity Share Capital`, itemized `Receivables`/
  `Inventory`/`Cash & Bank`), while the manual-upload parser expects
  "BalanceSheet" / "P&L" with coarser names. These would never have
  worked together even in the original Streamlit app. I wrote a
  dedicated parser (`screener_downloaded_parser.py`) for the
  auto-download format that uses the more precise fields directly
  instead of guessing percentages — tested against a synthetic file
  matching the documented format, confirmed correct extraction.
- Failure modes (missing cookies, expired session, 403 from the site)
  all degrade to clean flashed messages instead of crashing — tested.

**What's still unverified**: the actual scrape against the live
Screener.in site. I have no network access to screener.in from here, so
`ScreenerDownloader.download_excel()`'s page-parsing logic (which reads
the live HTML) has not been exercised against a real response — only
the downstream conversion/parsing has been tested with synthetic data.
This needs your first real run with your actual `screener_cookies.pkl`
in `instance/`. If Screener.in's page structure has changed since this
was written, this is where it'll break — tell me the error and I'll fix
it fast.

## What I'd actually recommend next

In priority order, if you want to keep closing gaps:
1. **Live-test everything above marked ✅** on your machine with real
   tickers/files — that's the highest-value next step, full stop.
2. PDF export (contained, testable without network, high visible value)
3. Bank/NBFC branch (contained to a well-defined set of functions already
   sitting untouched in `dcf_engine.py`)
4. Per-year override grids (frontend-heavy, lower urgency)
5. Screener.in auto-download (needs to be built and tested together,
   live, given the network/credential considerations above)
6. Stock price comparison tab, 3D peer dashboard (nice-to-have, lowest
   urgency of what's left)
7. Deployment (Phase 7)
