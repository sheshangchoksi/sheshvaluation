#!/usr/bin/env bash
# Render build command for the NATIVE (non-Docker) Python service option.
# If you deploy via the Dockerfile instead, Render ignores this — the
# Dockerfile's own RUN pip install step handles it.
set -e

pip install --upgrade pip
pip install -r requirements.txt

# Kaleido (used for chart images in PDF export) needs a local Chrome/Chromium.
# On Render's native Python runtime there's no apt-get access, so this
# downloads a Chromium build kaleido can use directly.
plotly_get_chrome -y || true

mkdir -p instance/uploads
