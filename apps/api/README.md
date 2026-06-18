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
  auth/
    base.py            AuthProvider Protocol + the AuthenticatedUser identity it returns.
    dev_token.py       HMAC-signed dev tokens — real per-user scoping with no IdP yet.
    factory.py         Config-driven selection of the auth backend.
  ratelimit/
    base.py            RateLimiter Protocol + QuotaWindow (allowed/remaining/reset).
    memory.py          In-process per-user daily limiter; Redis-ready behind the Protocol.
    factory.py         Config-driven selection of the limiter backend.
  schemas/
    cards.py           Domain DTOs: CardIdentity, RecognitionResult, PriceQuote.
    scan.py            /scan request + response contract (resolved | needs_confirmation).
    collection.py      Add-to-collection request + valued collection response.
    portfolio.py       Portfolio total + snapshot/history response.
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
    scan.py            Orchestration: recognize → (confirm | price) → persist → response.
    collection.py      Add a card; value the holdings in € via the pricing seam.
    portfolio.py       Total the collection, snapshot it, read the value-over-time series.
  db/
    base.py            Declarative Base + naming convention + timestamp mixin.
    types.py           Portable GUID / UTC-timestamp seam (Postgres ↔ SQLite).
    session.py         Async engine + session factory + unit-of-work scope.
    erasure.py         Right-to-erasure strategy (cascade + data-lake purge manifest).
    models/            User, Card, CollectionItem, PortfolioSnapshot, ScanRecord,
                       PriceObservation, and the persisted enums.
    repositories/      Typed async data access — the only layer that issues queries.
  api/
    health.py, scan.py, collection.py, portfolio.py, dependencies.py
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
| `HOLOFY_AUTH_PROVIDER`               | `dev_token`      | `dev_token` (real IdP swaps in behind the seam) |
| `HOLOFY_AUTH_DEV_SECRET`             | _(dev default)_  | Signs dev tokens; set a real secret outside `local` |
| `HOLOFY_RATE_LIMIT_PROVIDER`         | `memory`         | `memory` (Redis backend lands behind the Protocol) |
| `HOLOFY_FREE_TIER_DAILY_SCANS`       | `8`              | Free-tier scan budget per user per UTC day      |

## Auth, scoping & quota

Every endpoint except `/health` is **user-scoped**: the caller is resolved from a
`Authorization: Bearer <token>` header to a persisted `User`, and a user only ever reads or
writes their own scans, collection, and portfolio. Authentication sits behind an
`AuthProvider` Protocol so the dev backend here is replaced wholesale by Clerk/Supabase
token verification later — no endpoint changes (ADR 0004).

The dev backend issues an HMAC-signed token (`<subject>.<signature>`); it is **not**
"always admin" — each subject scopes to a distinct user, and a forged/tampered token fails
verification. A missing token is `401 not_authenticated`; a present-but-bad one is
`401 invalid_credential`. The user row is provisioned on first sight of a token, so no
separate signup call is needed in dev. Mint a token for local use:

```bash
PYTHONPATH=.deps:. python3 -c \
  "from app.auth import mint_dev_token; print(mint_dev_token('collector-1', secret='dev-insecure-do-not-use-in-production'))"

curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/portfolio
```

`HOLOFY_AUTH_DEV_SECRET` signs the tokens; it is dev-only and must be set to a real secret
(or the backend swapped) outside `local`.

**Scan quota** protects per-scan COGS: the free ("Collector") tier is **8 ID scans/day**
(master plan §4), enforced per user before any recognition cost is spent. Over the budget
returns `429 quota_exceeded` with `details.limit` and `details.reset_seconds`. The limiter
is an in-process daily counter behind a `RateLimiter` Protocol; a Redis backend drops in for
the multi-instance gateway. Tune the limit with `HOLOFY_FREE_TIER_DAILY_SCANS`.

## Endpoints

- `GET /health` — status, version, active provider backends, data region. **(no auth)**
- `POST /scan` — `{ "bundle_id", "image_count"?, "training_consent"?, "consent_note"? }`
  → `ScanResponse`. Persists a `ScanRecord` (training consent **off** unless explicitly
  opted in) and, on a resolved card, lands it in the catalog so it is addable straight away.
  - `outcome: "resolved"` → `card` (identity + price).
  - `outcome: "needs_confirmation"` → `choices` (top-2) + `price_delta`.
- `POST /collection` — `{ "canonical_id", "condition"?, "quantity"?, "acquired_price_eur"?,
  "acquired_on"? }` → the added holding with its current € valuation. The card must already
  exist in the catalog (scan or look it up first), else `404 card_not_found`.
- `GET /collection` — the user's holdings, each with a current € unit/line value, plus the
  collection `total_value_eur`.
- `GET /portfolio` — the live collection total in € (value, cost basis, item count).
- `POST /portfolio/snapshots` — pin the current total into the append-only history.
- `GET /portfolio/snapshots?limit=` — newest-first value-over-time series for the chart.

Errors share one envelope: `{ "error": { "code", "message", "details" } }`, with the
request id echoed in `X-Request-ID`.
