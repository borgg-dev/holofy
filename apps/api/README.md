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
  api/
    health.py, scan.py, dependencies.py
tests/                 Unit (providers, service) + API (TestClient) coverage.
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
