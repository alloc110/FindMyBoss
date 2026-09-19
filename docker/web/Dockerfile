# =========================================================
# FindMyBoss — Web Studio & API Gateway
# Base: python:3.12-slim (siêu nhẹ — không có Chromium/Tectonic)
# Role: Microservice 1 — UI Dashboard, AI Tailoring, Settings
# =========================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Ho_Chi_Minh

WORKDIR /app

# Minimal OS deps: timezone, curl (for healthcheck & httpx CA), ca-certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (web-only: no Playwright, no Tectonic)
COPY docker/web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY web/ /app/web/
COPY services/ /app/services/
COPY templates/ /app/templates/
COPY config.py /app/config.py
COPY models/ /app/models/

# Ensure data and logs directories exist (actual content comes from volumes)
RUN mkdir -p /app/data /app/data/cvs /app/logs

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:8000/api/stats || exit 1

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
