#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure runtime directories exist on host
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

LOG_FILE="$PROJECT_DIR/logs/scraper_$(date '+%Y%m%d').log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Starting FindMyBoss Scraper Container..." | tee -a "$LOG_FILE"

# Execute ephemeral container: auto-removed (--rm) on completion
docker compose run --rm scraper 2>&1 | tee -a "$LOG_FILE"

STATUS="${PIPESTATUS[0]}"

if [ "$STATUS" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Scraping finished successfully. Container shutdown and cleaned up." | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Scraper exited with status $STATUS. Container cleaned up." | tee -a "$LOG_FILE"
fi

exit "$STATUS"
