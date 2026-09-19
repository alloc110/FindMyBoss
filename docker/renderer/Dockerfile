# =========================================================
# Stage 1: Download & verify Tectonic binary
# =========================================================
FROM python:3.12-slim AS tectonic-downloader

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download Tectonic v0.15.0 binary (stable, pinned version)
RUN TECTONIC_VERSION="0.15.0" && \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ARCH_TAG="x86_64-unknown-linux-musl"; \
    elif [ "$ARCH" = "aarch64" ]; then ARCH_TAG="aarch64-unknown-linux-musl"; \
    else ARCH_TAG="x86_64-unknown-linux-musl"; fi && \
    curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-${ARCH_TAG}.tar.gz" \
    -o /tmp/tectonic.tar.gz && \
    tar -xzf /tmp/tectonic.tar.gz -C /tmp && \
    mv /tmp/tectonic /usr/local/bin/tectonic && \
    chmod +x /usr/local/bin/tectonic

# =========================================================
# Stage 2: Final runtime image
# =========================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Ho_Chi_Minh

WORKDIR /app

# Runtime system dependencies for XeTeX/LaTeX font rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    fontconfig \
    fonts-liberation \
    fonts-dejavu-core \
    libgraphite2-3 \
    libharfbuzz0b \
    libfreetype6 \
    libfontconfig1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy Tectonic binary from builder stage
COPY --from=tectonic-downloader /usr/local/bin/tectonic /app/bin/tectonic
RUN chmod +x /app/bin/tectonic

# Install Python requirements (minimal — no Playwright, no Google AI)
COPY docker/renderer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what this microservice needs
COPY services/renderer_microservice.py /app/services/renderer_microservice.py
COPY services/latex_engine.py /app/services/latex_engine.py
COPY services/__init__.py /app/services/__init__.py
COPY config.py /app/config.py
COPY templates/ /app/templates/

# Create directories
RUN mkdir -p /app/data/cvs /app/logs /app/bin

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "services.renderer_microservice:app", "--host", "0.0.0.0", "--port", "8001"]
