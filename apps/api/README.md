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
    grading.py         /pregrade contract: SubScore, GradeProbabilityRange (range, never a
                       single grade), estimated | retake outcomes + disclaimer.
    authenticity.py    /authenticity contract: AuthenticitySignal, RiskBand (a three-band risk
                       flag, never a fake/genuine verdict), assessed | retake | not_assessed.
    collection.py      Add-to-collection request + valued collection response.
    portfolio.py       Portfolio total + snapshot/history response.
  grading/
    centering.py       In-house pixel-level centering measurement (numpy; promoted Spike D).
    capture_store.py   CaptureStore seam: resolves a capture_ref to image bytes (mock = synthetic).
  authenticity/
    catalog_existence.py  CatalogExistenceChecker seam + the tri-state existence verdict.
    reference_catalog.py  Reference-backed existence check (the mock); catches a never-printed
                          variant — the strongest single fake signal.
  providers/
    base.py            RecognitionProvider / PricingProvider / GradingProvider /
                       AuthenticityProvider Protocols.
    factory.py         Config-driven selection of concrete providers.
    recognition/
      mock.py          Deterministic fixtures incl. the low-confidence top-2 case.
    pricing/
      tcgdex.py        Shared TCGdex Cardmarket client (the spikes' helpers, consolidated).
      tcgdex_provider.py  Real PricingProvider over TCGdex (no key).
      mock.py          Offline PricingProvider for tests / keyless runs.
    grading/
      mock.py          Deterministic bought sub-scores (corners/edges/surface) incl. a
                       poor-surface and a low-confidence fixture; Ximilar /v2/grade drops in later.
    authenticity/
      mock.py          Deterministic per-signal reads (print-pattern/holo/font/cardstock) incl.
                       strong-authentic, mixed and poor-capture fixtures; the CV ensemble later.
  services/
    scan.py            Orchestration: recognize → (confirm | price) → persist → response.
    pregrade.py        Compose in-house centering + bought sub-scores → grade probability
                       range; refuse (retake) on a capture too poor to grade honestly.
    authenticity.py    Compose visual signals + catalog cross-check → a risk *band* (never a
                       verdict); value-gate, refuse (retake), never-printed-variant override.
    collection.py      Add a card; value the holdings in € via the pricing seam.
    portfolio.py       Total the collection, snapshot it, read the value-over-time series.
  db/
    base.py            Declarative Base + naming convention + timestamp mixin.
    types.py           Portable GUID / UTC-timestamp seam (Postgres ↔ SQLite).
    session.py         Async engine + session factory + unit-of-work scope.
    erasure.py         Right-to-erasure strategy (cascade + data-lake purge manifest).
    models/            User, Card, CollectionItem, PortfolioSnapshot, ScanRecord,
                       PreGradeRecord, AuthenticityRecord, PriceObservation, and the
                       persisted enums.
    repositories/      Typed async data access — the only layer that issues queries.
  api/
    health.py, scan.py, pregrade.py, authenticity.py, collection.py, portfolio.py,
    dependencies.py
migrations/            Alembic (env reads the app's DATABASE_URL; initial + pregrade_records
                       + authenticity_records).
tests/                 Unit (providers, centering, pregrade composition, persistence) +
                       API (TestClient) coverage.
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
| Grading      | `MockGradingProvider`     | — (Ximilar `/v2/grade` lands behind the Protocol) |
| Authenticity | `MockAuthenticityProvider` | — (a CV ensemble lands behind the Protocol)       |
| Capture store| `MockCaptureStore` (synthetic captures by ref) | — (EU-region object storage)        |

Select per environment via `HOLOFY_RECOGNITION_PROVIDER`, `HOLOFY_PRICING_PROVIDER`,
`HOLOFY_GRADING_PROVIDER` and `HOLOFY_AUTHENTICITY_PROVIDER`.

The **catalog-existence cross-check is *not* a provider** — it is a deterministic reference-DB
lookup the authenticity service owns (the analogue of in-house centering, kept out of the
`GradingProvider` seam). The mock answers from a small fixed set of known printings so the
never-printed-variant case — the strongest single fake signal — is testable with no catalog
sync; the real reference-DB-backed checker drops in behind the `CatalogExistenceChecker`
Protocol (ADR 0006).

**Centering is *not* mocked** — it is measured in-house (`app/grading/centering.py`, pure
numpy, promoted from Spike D). The grading provider only supplies the three *bought*
sub-grades (corners, edges, surface); the pre-grade service composes them with the in-house
centering into an honest grade probability **range** — never a single grade (charter §3.1) —
and refuses with a "retake" signal when a capture is too poor to grade honestly.

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
| `HOLOFY_GRADING_PROVIDER`            | `mock`           | `mock` (bought corners/edges/surface)           |
| `HOLOFY_AUTHENTICITY_PROVIDER`       | `mock`           | `mock` (visual print/holo/font/cardstock reads) |
| `HOLOFY_RECOGNITION_CONFIRM_THRESHOLD` | `0.85`         | Below this top-1 confidence → confirm prompt    |
| `HOLOFY_PREGRADE_MIN_CENTERING_CONFIDENCE` | `0.4`      | Below this the pre-grade refuses (retake)       |
| `HOLOFY_AUTHENTICITY_MIN_VALUE_EUR`  | `50.0`           | Below this € value → `not_assessed` (cheap cards aren't faked) |
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
the multi-instance gateway. Tune the limit with `HOLOFY_FREE_TIER_DAILY_SCANS`. `/pregrade`
and `/authenticity` share the same daily budget (one quota key), so they can't be used to
sidestep the scan cap.

## Endpoints

- `GET /health` — status, version, active provider backends, data region. **(no auth)**
- `POST /scan` — `{ "bundle_id", "image_count"?, "training_consent"?, "consent_note"? }`
  → `ScanResponse`. Persists a `ScanRecord` (training consent **off** unless explicitly
  opted in) and, on a resolved card, lands it in the catalog so it is addable straight away.
  - `outcome: "resolved"` → `card` (identity + price).
  - `outcome: "needs_confirmation"` → `choices` (top-2) + `price_delta`.
- `POST /pregrade` — `{ "capture_ref", "card_id"? }` → `PregradeResponse`. Composes the
  in-house centering measurement with bought corners/edges/surface into an honest grade
  **probability range**, and persists a `PreGradeRecord`. Every response carries a
  `disclaimer`: it is a pre-screen, decision support, **not** an official grade.
  - `status: "estimated"` → `probability` (`likely_low`/`likely_high` + `at_least`/
    `p_at_least` — there is deliberately no single "grade" field), `sub_scores` (the four
    PSA axes), and an overall `confidence`. Low capture/centering confidence widens the
    range and lowers `confidence` rather than faking precision.
  - `status: "retake"` → `reasons` (no range). A capture too poor to grade honestly — a
    full-bleed card with no border, a washed-out/skewed border below the confidence floor —
    is returned as a clear typed **200**, never a 500. Tune the floor with
    `HOLOFY_PREGRADE_MIN_CENTERING_CONFIDENCE`.
  - An unresolvable `capture_ref` (unknown/expired upload) is `404 capture_not_found` —
    distinct from a gradeable-but-poor capture.
- `POST /authenticity` — `{ "capture_ref", "card_id" }` → `AuthenticityResponse`. Composes the
  four visual signals (print-pattern, holo, font/layout, cardstock) with a catalog-existence
  cross-check into a private authenticity **risk band**, and persists an `AuthenticityRecord`.
  Every response carries a `disclaimer`: it is a risk signal for the owner, **not** a verdict
  that a card is genuine or counterfeit, and **not** an assessment of any seller (charter §3.5).
  There is no `is_fake`/`is_genuine`/`verdict` field anywhere — the most adverse output is
  `elevated_risk`.
  - `status: "assessed"` → `assessment` with `risk_band`
    (`strong_signals`/`inconclusive`/`elevated_risk` — never a boolean), the per-signal
    `signals` (incl. the catalog cross-check), an overall `confidence`, and
    `recommend_authentication`. A `(set, number, variant, era)` that was **never printed**
    floors the band at `elevated_risk` regardless of clean visuals.
  - `status: "not_assessed"` → `reasons`. Below `HOLOFY_AUTHENTICITY_MIN_VALUE_EUR` (cheap
    commons aren't faked) the screen is skipped rather than fake-scored — a typed **200**.
  - `status: "retake"` → `reasons`. A capture too poor to read the signals refuses with
    coaching, never a confident wrong band — a typed **200**, not a 500.
  - The `card_id` must already exist in the catalog (the cross-check and value gate need a
    resolved identity), else `404 card_not_found`; an unresolvable `capture_ref` is
    `404 capture_not_found`.
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
