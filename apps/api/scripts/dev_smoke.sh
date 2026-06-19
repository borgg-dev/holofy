#!/usr/bin/env bash
# One-shot dev smoke: fresh DB -> migrate -> boot the API -> drive the full journey -> tear down.
# Proves the whole product runs end to end in dev mode, mock-first, with no API keys.
set -euo pipefail

cd "$(dirname "$0")/.."   # apps/api
export PYTHONPATH="${PYTHONPATH:-}:.deps:."
# The interpreter must be >= 3.11 (StrEnum). Boxes where `python3` is older can point this
# at a newer one (e.g. HOLOFY_SMOKE_PYTHON=python3.11) without touching the system default.
PY="${HOLOFY_SMOKE_PYTHON:-python3}"
PORT="${HOLOFY_SMOKE_PORT:-8099}"
DB="./holofy_smoke.db"
export HOLOFY_DATABASE_URL="sqlite+aiosqlite:///${DB}"
export HOLOFY_SMOKE_BASE_URL="http://127.0.0.1:${PORT}"
# Keep real uploaded bytes in process so the journey exercises the actual upload->store->
# scan/pre-grade path, not synthetic-by-reference captures.
export HOLOFY_CAPTURE_STORAGE=memory
# This is the FAST mock journey — pin the mock backends explicitly, now that the app's
# production defaults are the real providers (in-house recognition, TCGdex). The owned-models
# journey on real pixels lives in dev_smoke_inhouse.sh.
export HOLOFY_RECOGNITION_PROVIDER=mock
export HOLOFY_PRICING_PROVIDER=mock
export HOLOFY_GRADING_PROVIDER=mock
export HOLOFY_AUTHENTICITY_PROVIDER=mock

rm -f "$DB"
"$PY" -m alembic upgrade head >/dev/null

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; rm -f "$DB"; }
trap cleanup EXIT

# Wait for the server to accept connections (no fixed sleep).
curl -s --retry 30 --retry-all-errors --retry-delay 1 -o /dev/null "${HOLOFY_SMOKE_BASE_URL}/health"

"$PY" scripts/smoke_journey.py
