#!/usr/bin/env bash
# One-shot dev smoke on Holofy's OWN models: fresh DB -> migrate -> boot the API with the
# in-house recognizer + grader -> drive the journey on real uploaded card images -> tear down.
# Proves the end-to-end product runs on owned intelligence (no vendor API, no keys).
set -euo pipefail

cd "$(dirname "$0")/.."   # apps/api
export PYTHONPATH="${PYTHONPATH:-}:.deps:."
PY="${HOLOFY_SMOKE_PYTHON:-python3}"
PORT="${HOLOFY_SMOKE_PORT:-8098}"
DB="./holofy_smoke_inhouse.db"
export HOLOFY_DATABASE_URL="sqlite+aiosqlite:///${DB}"
export HOLOFY_SMOKE_BASE_URL="http://127.0.0.1:${PORT}"
# Owned intelligence + real uploaded bytes. Catalog stays in-memory seeds (the rendered cards
# match them); flip to HOLOFY_CATALOG_PROVIDER=tcgdex for the live catalog.
export HOLOFY_CAPTURE_STORAGE=memory
export HOLOFY_RECOGNITION_PROVIDER=inhouse
export HOLOFY_GRADING_PROVIDER=inhouse
export HOLOFY_AUTHENTICITY_PROVIDER=inhouse
# This journey resolves the invented seed cards, so pin the in-memory seed catalog and the
# mock pricer that knows their prices (production defaults are the live TCGdex catalog + pricer).
export HOLOFY_CATALOG_PROVIDER=inmemory
export HOLOFY_PRICING_PROVIDER=mock
# The smoke mints dev tokens; pin that bearer (production default is the session token).
export HOLOFY_AUTH_PROVIDER=dev_token

rm -f "$DB"
"$PY" -m alembic upgrade head >/dev/null

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; rm -f "$DB"; }
trap cleanup EXIT

curl -s --retry 30 --retry-all-errors --retry-delay 1 -o /dev/null "${HOLOFY_SMOKE_BASE_URL}/health"

"$PY" scripts/smoke_journey_inhouse.py
