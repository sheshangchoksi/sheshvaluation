#!/usr/bin/env bash
# Starts the app with gunicorn, binding to Render's dynamic $PORT.
# Render sets $PORT itself (default 10000) — do not hardcode a port.
set -e

: "${PORT:=10000}"
: "${WEB_CONCURRENCY:=1}"      # free tier has ~512MB RAM; keep worker count low
: "${GUNICORN_THREADS:=4}"     # use threads for concurrency instead of more workers
: "${GUNICORN_TIMEOUT:=120}"   # Yahoo Finance/Screener.in fetches can be slow

mkdir -p instance/uploads

export FLASK_APP=run.py
echo "Running database migrations..."
flask db upgrade

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY}" \
  --threads "${GUNICORN_THREADS}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  run:app
