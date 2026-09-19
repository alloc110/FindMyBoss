#!/usr/bin/env bash
set -e

# Runner for FindMyBoss Web UI & ATS CV Studio
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Ensure tectonic binary is ready
if [ ! -f "bin/tectonic" ]; then
    echo "⚙️ Initializing Tectonic LaTeX compiler..."
    bash ./scripts/setup_tectonic.sh
fi

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo "🎯 Launching FindMyBoss Web Studio on http://localhost:$PORT"
echo "=========================================================="

exec ./venv/bin/uvicorn web.app:app --host "$HOST" --port "$PORT" --reload
