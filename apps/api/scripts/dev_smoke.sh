#!/usr/bin/env bash
# One-shot dev smoke: fresh DB -> migrate -> boot the API -> drive the full journey -> tear down.
# Proves the whole product runs end to end in dev mode, mock-first, with no API keys.
set -euo pipefail

cd "$(dirname "$0")/.."   # apps/api
export PYTHONPATH="${PYTHONPATH:-}:.deps:."
PORT="${HOLOFY_SMOKE_PORT:-8099}"
DB="./holofy_smoke.db"
export HOLOFY_DATABASE_URL="sqlite+aiosqlite:///${DB}"
export HOLOFY_SMOKE_BASE_URL="http://127.0.0.1:${PORT}"

rm -f "$DB"
python3 -m alembic upgrade head >/dev/null

python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; rm -f "$DB"; }
trap cleanup EXIT

# Wait for the server to accept connections (no fixed sleep).
curl -s --retry 30 --retry-all-errors --retry-delay 1 -o /dev/null "${HOLOFY_SMOKE_BASE_URL}/health"

python3 scripts/smoke_journey.py
