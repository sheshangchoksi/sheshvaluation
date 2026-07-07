# Deploying to Render

## What you get for free, and what you don't

Verified against Render's current docs (checked while building this):

- Free web services **spin down after 15 minutes of no traffic** and take
  30–60 seconds to wake back up on the next request. Fine for personal/
  small-team use; annoying if you hit it right after it's slept.
- Free web services get **750 instance-hours/month** — if you're the only
  user and it sleeps when idle, you won't come close to that limit.
- **No persistent disk on free tier.** Uploaded Excel files and generated
  PDFs are deleted right after use anyway, so this costs nothing there.
- **Free Postgres databases expire 30 days after creation** unless
  upgraded to a paid plan before then. This app's logins and (once
  built) valuation history live in Postgres — mark your calendar, or
  budget for the paid database tier if you want this to keep working
  past the first month. There's no free-tier workaround for this one;
  it's a hard Render policy.
- Outbound bandwidth and build minutes are also capped on free, but
  you'd need real traffic to hit those limits.

## Logins are self-service now (no Secret File needed)

Earlier versions of this app used a `users.json` Secret File for a fixed
login list. That's gone — signup is now a real page backed by Postgres
(`/auth/signup`), with Argon2 password hashing and account lockout after
5 failed attempts. Nothing to prepare locally for this anymore; once
deployed, just visit `/auth/signup`.

If you don't want strangers signing up on a public URL, set a
`SIGNUP_CODE` environment variable in Render (Environment tab, plain env
var, not a Secret File) — the signup form will then require that code.

## One-time setup, before your first deploy

**1. (Optional) Convert your Screener.in cookies to JSON**, if you want
auto-download from Screener.in:

```powershell
python scripts\convert_cookies_to_json.py C:\path\to\screener_cookies.pkl
```

This writes `screener_cookies.json` next to it. Open that file, copy
its contents — you'll paste it into Render in step 3.

## Deploying

**2. Push this repo to GitHub** (Render deploys from a Git repo — `git`
commands are the same on Windows as anywhere else; use Git Bash, or
GitHub Desktop if you'd rather not use the command line).

Note: `start.sh` and `build.sh` are bash scripts, but you never run them
yourself on Windows — they only execute inside Render's Linux container
during build/deploy. Nothing to install locally for these.

**3. In the Render Dashboard: New → Blueprint → connect your repo.**
Render reads `render.yaml` and sets up both the web service *and* a free
Postgres database, and wires `DATABASE_URL` between them automatically —
this is the one significant advantage of the Blueprint route over
setting the service up by hand, so it's worth using here.
- Once the service exists, go to **Environment** in the left pane:
  - Under **Secret Files**, click **+ Add Secret File** (only needed if
    you want Screener.in auto-download):
    - Filename: `screener_cookies.json` → paste the contents from step 1.
  - `SECRET_KEY` and `DATABASE_URL` are already set for you by the
    Blueprint. Add `SIGNUP_CODE` here too (plain env var) if you want to
    gate signup.
- Save — Render redeploys automatically. `start.sh` runs
  `flask db upgrade` on every deploy, so the `users` table gets created
  automatically on this first deploy — no manual migration step needed.

**4. Confirm it's up**: visit `https://<your-service>.onrender.com/healthz`
— should return `{"status": "ok"}`. Then go to `/auth/signup` and create
your account.

## Notes specific to this app

- **PDF charts need Chrome.** The Dockerfile installs `chromium` and
  points `kaleido` at it. If you switch to Render's native (non-Docker)
  Python runtime instead, `build.sh` runs `plotly_get_chrome` to fetch
  one — either path should work, but the Docker path is what's actually
  been exercised here.
- **Yahoo Finance rate limiting**: per your own testing, this clears up
  once deployed (Render's IPs aren't hitting the same local-machine
  throttling you saw). `curl_cffi` is already in `requirements.txt` as
  the primary defense either way.
- **Screener.in auto-download**: still unverified against the live site
  from my side (see `PARITY.md`) — this deploy is genuinely the first
  real test of it. If it breaks, the error message should tell you
  whether it's an auth/cookie problem or something else.
- **Memory**: free tier is ~512MB RAM. `start.sh` runs gunicorn with 1
  worker + 4 threads rather than multiple worker processes, to stay
  within that comfortably. If you upgrade off free tier later, bump
  `WEB_CONCURRENCY` via an environment variable.
