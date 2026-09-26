#!/usr/bin/env bash
set -e

# Runner for FindMyBoss Web UI & ATS CV Studio
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# Determine python/uvicorn executable (supports Linux venv & Windows Git Bash venv)
if [ -x "./venv/bin/uvicorn" ]; then
    UVICORN_BIN="./venv/bin/uvicorn"
elif [ -x "./venv/Scripts/uvicorn.exe" ]; then
    UVICORN_BIN="./venv/Scripts/uvicorn.exe"
else
    UVICORN_BIN="uvicorn"
fi

echo "=========================================================="
echo "🎯 Launching FindMyBoss Web Studio on http://localhost:$PORT"
echo "=========================================================="

exec "$UVICORN_BIN" web.app:app --host "$HOST" --port "$PORT" --reload
