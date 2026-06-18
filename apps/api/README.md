# Holofy API

FastAPI backend for the scan loop: a capture bundle is recognized into a card identity,
priced in € (Cardmarket), and returned — or, when the recognizer isn't confident, surfaced
as a top-2 confirm prompt with the price delta rather than a silent guess.

Phase 1, mock-first: every external capability sits behind a swappable Protocol with a
working mock, so the whole service runs with **no keys and no network**. Real providers
(Ximilar recognition, Cardmarket pricing) drop in behind the same seam later.

## Layout

```
app/
  config.py            Typed settings (pydantic-settings). EU data region, provider switches.
  main.py              App factory: lifespan, CORS, request-id middleware, error handlers.
  core/
    errors.py          HolofyError hierarchy + the single error envelope.
    logging.py         Structured JSON logging with per-request id.
  schemas/
    cards.py           Domain DTOs: CardIdentity, RecognitionResult, PriceQuote.
    scan.py            /scan request + response contract (resolved | needs_confirmation).
  providers/
    base.py            RecognitionProvider / PricingProvider Protocols.
    factory.py         Config-driven selection of concrete providers.
    recognition/
      mock.py          Deterministic fixtures incl. the low-confidence top-2 case.
    pricing/
      tcgdex.py        Shared TCGdex Cardmarket client (the spikes' helpers, consolidated).
      tcgdex_provider.py  Real PricingProvider over TCGdex (no key).
      mock.py          Offline PricingProvider for tests / keyless runs.
  services/
    scan.py            Orchestration: recognize → (confirm | price) → response DTO.
  db/
    base.py            Declarative Base + naming convention + timestamp mixin.
    types.py           Portable GUID / UTC-timestamp seam (Postgres ↔ SQLite).
    session.py         Async engine + session factory + unit-of-work scope.
    erasure.py         Right-to-erasure strategy (cascade + data-lake purge manifest).
    models/            User, Card, CollectionItem, PortfolioSnapshot, ScanRecord,
                       PriceObservation, and the persisted enums.
    repositories/      Typed async data access — the only layer that issues queries.
  api/
    health.py, scan.py, dependencies.py
migrations/            Alembic (env reads the app's DATABASE_URL; one initial revision).
tests/                 Unit (providers, service, persistence) + API (TestClient) coverage.
```

## Database

Postgres is the production target — EU-region (`asyncpg`), holding portfolios, scan
history, and the persisted € price observations that become our own price history. Tests
run the **same** ORM models on in-memory SQLite (`aiosqlite`), so no Postgres or Docker is
needed to develop or test. Portability lives in two places: `db/types.py` (a `GUID` and
UTC timestamp that degrade from Postgres-native to SQLite) and the naming convention on
`Base.metadata` (so a constraint has the same name on both backends, which is what keeps
migrations applicable to either).

**Schema shape:** `User` (auth linkage is a later, additive slice) owns `CollectionItem`,
`ScanRecord`, and `PortfolioSnapshot` (all `ON DELETE CASCADE`). `Card` is the shared
canonical catalog the disambiguation tuple `(set, number, variant, language)` keys; it and
`PriceObservation` are market/reference data and are never erased with a user.

**Consent & erasure (the moat, safely):** `ScanRecord.training_consent` defaults to
`False` — a scan is never training-eligible unless the user explicitly opted in; consent is
separate from app-usage and revocable (`consent_revoked_at`), with a row-level check that
the two can't both be set. `db/erasure.py` documents how a delete propagates: the cascade
clears Postgres, and `plan_erasure` enumerates the object-storage keys and consented scan
ids so an out-of-band job can purge images and any data-lake copies in the same transaction.

### Migrations (Alembic)

The migration URL is read from `HOLOFY_DATABASE_URL` in `migrations/env.py`, not from
`alembic.ini`, so migrations target the same database the app does and no secret is
committed. (No `alembic` console script under `--target` installs; invoke via `-m`.)

```bash
cd apps/api

# Apply to local SQLite (default db file)
PYTHONPATH=.deps:. python3 -m alembic upgrade head

# Apply to prod Postgres
HOLOFY_DATABASE_URL="postgresql+asyncpg://user:pass@host/holofy" \
  PYTHONPATH=.deps:. python3 -m alembic upgrade head

# After a model change: autogenerate the next revision, then review it
PYTHONPATH=.deps:. python3 -m alembic revision --autogenerate -m "describe change"

# Verify models and migrations are in sync (CI guard)
PYTHONPATH=.deps:. python3 -m alembic check
```

## What's mocked vs real

| Capability   | Mock                      | Real                                              |
|--------------|---------------------------|---------------------------------------------------|
| Recognition  | `MockRecognitionProvider` | — (Ximilar/on-device lands behind the Protocol)   |
| Pricing      | `MockPricingProvider`     | `TcgdexPricingProvider` (open TCGdex API, no key)  |

Select per environment via `HOLOFY_RECOGNITION_PROVIDER` and `HOLOFY_PRICING_PROVIDER`.

## Run

No `python3-venv` on this box; install into a local target dir and put it on the path.

```bash
cd apps/api
pip install --target .deps -r requirements.txt

# Tests
PYTHONPATH=.deps:. .deps/bin/pytest -q

# Dev server (defaults to mock providers — no keys needed)
PYTHONPATH=.deps:. .deps/bin/uvicorn app.main:app --reload
# OpenAPI docs at http://127.0.0.1:8000/docs
```

With a normal `venv` available, the usual `python -m venv .venv && pip install -r
requirements.txt && pytest` / `uvicorn app.main:app` applies.

### Try the real pricing path (no key)

```bash
HOLOFY_PRICING_PROVIDER=tcgdex PYTHONPATH=.deps:. .deps/bin/uvicorn app.main:app
```

## Configuration

All settings are env vars prefixed `HOLOFY_` (or a `.env` file). Notable ones:

| Var                                  | Default          | Note                                            |
|--------------------------------------|------------------|-------------------------------------------------|
| `HOLOFY_ENVIRONMENT`                 | `local`          | `local` / `staging` / `production`              |
| `HOLOFY_DATA_REGION`                 | `eu-central-1`   | GDPR residency; echoed by `/health`             |
| `HOLOFY_DATABASE_URL`                | `sqlite+aiosqlite:///./holofy.db` | Prod: `postgresql+asyncpg://…` in EU |
| `HOLOFY_CORS_ALLOW_ORIGINS`          | _(empty)_        | Deny-by-default; JSON list per environment      |
| `HOLOFY_RECOGNITION_PROVIDER`        | `mock`           | `mock`                                          |
| `HOLOFY_PRICING_PROVIDER`            | `mock`           | `mock` / `tcgdex`                               |
| `HOLOFY_RECOGNITION_CONFIRM_THRESHOLD` | `0.85`         | Below this top-1 confidence → confirm prompt    |

## Endpoints

- `GET /health` — status, version, active provider backends, data region.
- `POST /scan` — `{ "bundle_id": "...", "image_count": 1 }` → `ScanResponse`.
  - `outcome: "resolved"` → `card` (identity + price).
  - `outcome: "needs_confirmation"` → `choices` (top-2) + `price_delta`.

Errors share one envelope: `{ "error": { "code", "message", "details" } }`, with the
request id echoed in `X-Request-ID`.
