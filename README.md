# DCF Valuation Engine — Flask edition

Migration of the Streamlit app to a standalone Flask app. See
`INVENTORY.md` for the full Phase 0 audit of what moved where and why.

## Status

See **`PARITY.md`** for the full, honest feature-by-feature comparison
against the original Streamlit app, and **`DEPLOY.md`** for step-by-step
Render deployment instructions.

- **Phase 0–4 — done.** Skeleton, Listed/Unlisted/Screener modes.
- **Phase 2B — done, extended this delivery.** Auto-fetch peers now also
  works in Unlisted mode (via a reference ticker, since unlisted
  companies have no ticker of their own).
- **Phase 6 (mostly done):** Bank/NBFC valuation branch, PDF export
  (Listed/Unlisted/Screener). Not done: PDF export for bank results,
  peer-comparison page inside PDFs (shape mismatch, documented in
  PARITY.md). **Stock price comparison tab: explicitly out of scope
  per your call, not building it.**
- **Phase 5 — done (this delivery).** Screener.in auto-download is live
  on the Screener Excel Mode page. Still genuinely untested against the
  live site (no network access on my end) — your deploy is the first
  real test.
- **Phase 7 — done (this delivery).** Dockerfile, `render.yaml`
  Blueprint, `start.sh`/`build.sh`, health check endpoint, and Render's
  Secret Files pattern wired in for `users.json` and Screener.in cookies
  (switched cookie storage to JSON — Render's Secret Files are
  plaintext, so the original binary `.pkl` format wouldn't have
  survived being pasted into the dashboard). Full walkthrough in
  `DEPLOY.md`.
- **3D peer comparison dashboard** — still not built.

## Project layout

```
app/
  __init__.py        # app factory (create_app)
  config.py          # settings, reads from environment
  extensions.py      # cache + login manager, initialized in create_app
  auth/              # login/logout, simple JSON user store
  dcf/               # dashboard + (eventually) listed/unlisted/screener routes
  logic/             # untouched business-logic modules copied from the
                      # old app (PDF export, screener downloader, ticker
                      # cache, Indian-market API fallbacks, peer fetcher)
  data/              # Excel templates + peer cache, copied as-is
  templates/
  static/
instance/            # not committed: users.json, uploads
run.py               # dev entrypoint
Dockerfile           # for Phase 7 deployment
requirements.txt
```

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then edit SECRET_KEY
export FLASK_APP=run.py          # Windows: set FLASK_APP=run.py

# create your login (repeat for each of "a few people")
flask create-user yourname yourpassword

flask run
# or: python run.py
```

Visit http://127.0.0.1:5000 — log in, and you'll land on the dashboard
with the three mode cards (all "Coming soon" until Phase 2+ lands).

## Run it with Docker

```bash
docker build -t dcf-engine .
docker run -p 5000:5000 --env-file .env dcf-engine
```

Note: `flask create-user` needs to be run once against the running
container (or bake a starter `instance/users.json` into the image) —
we'll wire this properly in Phase 7 when we pick the actual host.

## What's NOT done yet (by design — later phases)

- Listed / Unlisted / Screener valuation workflows (Phase 2, 5)
- Plotly charts in templates (Phase 3)
- Excel/PDF upload & download routes (Phase 4)
- Peer comparison, auto-download from screener.in (Phase 5)
- Deployment to a live free host (Phase 7)
