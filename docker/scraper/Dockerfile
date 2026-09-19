# =========================================================
# FindMyBoss — Job Scraper & Crawler Worker
# Base: python:3.12-slim + Playwright Chromium
# Role: Microservice 3 — Job Harvester from Vietnamese portals
# =========================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Ho_Chi_Minh \
    # Playwright uses system Chromium installed via playwright install --with-deps
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System packages: timezone, curl (health checks), sqlite3
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages first (cached layer unless requirements change)
COPY docker/scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with all system dependencies
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy only what the scraper microservice needs
# Crawler modules
COPY crawl/ /app/crawl/
COPY services/scraper_microservice.py /app/services/scraper_microservice.py
COPY services/storage.py /app/services/storage.py
COPY services/__init__.py /app/services/__init__.py
COPY config.py /app/config.py
COPY main.py /app/main.py

# Create runtime directories
RUN mkdir -p /app/data /app/logs

EXPOSE 8002

HEALTHCHECK --interval=20s --timeout=10s --retries=3 --start-period=30s \
  CMD curl -f http://localhost:8002/health || exit 1

CMD ["uvicorn", "services.scraper_microservice:app", "--host", "0.0.0.0", "--port", "8002"]
