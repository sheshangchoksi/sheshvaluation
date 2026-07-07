FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    chromium \
    && rm -rf /var/lib/apt/lists/*

ENV KALEIDO_EXECUTABLE_PATH=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

RUN mkdir -p instance/uploads

# Render sets $PORT itself at runtime (default 10000) — do NOT hardcode
# EXPOSE/bind to a fixed port. start.sh reads $PORT dynamically.
EXPOSE 10000

CMD ["./start.sh"]
