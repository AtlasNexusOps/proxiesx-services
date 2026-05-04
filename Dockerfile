# Python 3.12 — Proxies.sx Scraper Services
FROM python:3.12-slim

WORKDIR /app

# System deps for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium --with-deps

# App code
COPY shared/ ./shared/
COPY amazon-tracker/ ./amazon-tracker/
COPY food-delivery/ ./food-delivery/
COPY server.py .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["python", "server.py", "--port", "8080", "--host", "0.0.0.0"]
