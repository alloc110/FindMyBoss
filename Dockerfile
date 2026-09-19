# Use official lightweight Python 3.12 slim image
FROM python:3.12-slim

# Set timezone and optimize python execution
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Ho_Chi_Minh

WORKDIR /app

# Install base OS dependencies for tzdata and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh \
    && mkdir -p /app/bin && mv tectonic /app/bin/tectonic && chmod +x /app/bin/tectonic

# Install Python requirements and Chromium with all native OS dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# Copy application source code
COPY . .

# Create volume mount directories
RUN mkdir -p /app/data /app/logs

# Default ephemeral execution: runs main.py and exits immediately upon completion
CMD ["python", "main.py"]
