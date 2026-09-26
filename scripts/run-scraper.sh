#!/usr/bin/env bash
set -e

# Navigate to the project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Determine python executable (prefer local venv Linux/Windows, then system python)
if [ -x "$PROJECT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
elif [ -x "$PROJECT_DIR/venv/Scripts/python.exe" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

mkdir -p "$PROJECT_DIR/logs"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting job scraping pipeline with $PYTHON_BIN..." >> "$PROJECT_DIR/logs/crawl_log.txt"

# Execute orchestrator
"$PYTHON_BIN" main.py "$@"

# Log completion metrics
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline execution finished successfully." >> "$PROJECT_DIR/logs/crawl_log.txt"
