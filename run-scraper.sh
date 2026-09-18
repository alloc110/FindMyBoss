#!/bin/bash
set -e

# Navigate to the absolute project root directory
PROJECT_DIR="/home/loc/job-scraper"
cd "$PROJECT_DIR" || { echo "CRITICAL: Project directory $PROJECT_DIR not found!" && exit 1; }

# Determine python executable (prefer local venv, then system user venv)
if [ -x "$PROJECT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
elif [ -x "/home/loc/venv/bin/python3" ]; then
    PYTHON_BIN="/home/loc/venv/bin/python3"
else
    PYTHON_BIN="$(command -v python3)"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting job scraping pipeline with $PYTHON_BIN..." >> "$PROJECT_DIR/crawl_log.txt"

# Execute orchestrator
"$PYTHON_BIN" main.py

# Log completion metrics
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline execution finished successfully." >> "$PROJECT_DIR/crawl_log.txt"