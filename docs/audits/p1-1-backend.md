# Audit — P1.1 Backend Skeleton (`apps/api/`)

- **Artifact:** Phase-1 mock-first scan API at `/home/borgg/holofy/apps/api/`
- **Auditor lenses:** Architecture (§3.2), Backend (§3.3), Security & Privacy (§3.5), Premium / Not-Generic (§3.6)
- **Date:** 2026-06-18
- **Method:** Full tree read, `pytest` run, real-provider boot, spike-vs-production diff, ADR cross-check.

## Test verification

```
PYTHONPATH=.deps:. .deps/bin/pytest -q  →  27 passed in 0.08s
```

27 tests pass, as claimed. They are **non-trivial**: they exercise both `/scan` outcomes,
the price-delta branch, the validation error envelope, the request-id round-trip, the
TCGdex client's trend→avg30 fallback, locale path construction, 404/no-pricing/transport
degradation, and the adapter's exception mapping. Network is hermetically mocked via
`httpx.MockTransport` (`tests/test_tcgdex_client.py:31`), so CI never touches the live API.
App also boots clean against the **real** provider (`HOLOFY_PRICING_PROVIDER=tcgdex`):
client built once in lifespan, `/health` returns 200 with no upstream call.

**Spike consolidation is genuine, not copy-paste.** `spikes/price_fetch/tcgdex_prices.py`
is a sync, CLI-oriented throwaway (`httpx.Client`, `staleness`, `_render`, `argparse`).
The production `app/providers/pricing/tcgdex.py` is a real refactor: async +
connection-pooled reusable client with `aclose()`/async-CM lifecycle, added `age_hours`
and `listing_url` properties, typed `TcgdexError` hierarchy, and the parse split into
`_price_from_card`. The spike's CLI/render cruft did **not** leak into production. No
duplicate `CardmarketPrice`/`fetch_cardmarket_price` definitions exist anywhere under
`app/`.

---

## Lens 1 — Architecture (§3.2)

| Criterion | Score | Notes |
|---|---|---|
| Fits documented design; ML stages swappable (buy→build) | 3 | `RecognitionProvider`/`PricingProvider` Protocols (`providers/base.py`) + config-driven `factory.py` are exactly the §3 seam. Real provider drops in with zero call-site change; verified by booting both backends. |
| Clear module boundaries, no leaky coupling, no premature abstraction | 3 | Clean layering: `schemas` (DTOs) ← `providers` ← `services` ← `api`. `canonical_id` decouples recognition from pricing (`schemas/cards.py:36`). Transport-neutral `PriceQuote` keeps httpx out of the service. No speculative interfaces. |
| Data-capture/consent loop honored where user content involved | 2 | No user content persisted yet (no portfolio/data-lake in this slice — correctly deferred to P1.4/Phase 3). `CaptureBundleRef` models references-not-bytes and `image_count` reasons about multi-angle capture without fetching images — the right primitive. Nothing to consent to yet, so no violation, but the loop itself is out of scope here. |
| Decisions traceable to an ADR | 3 | Code cites ADR 0001 (pricing) and 0002 (variant confirm) at the exact decision points (`config.py:9`, `mock.py:11`, `schemas/cards.py:31`). All three ADRs exist under `docs/adr/` and match the cited content. |

**Lens avg: 2.75 — every criterion ≥2. PASS.**

---

## Lens 2 — Backend (§3.3)

| Criterion | Score | Notes |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | App-factory pattern, lifespan-managed providers, `Depends` wiring, `StrEnum`, `from __future__ import annotations`, frozen pydantic DTOs, `Decimal` for money with str round-trip (`tcgdex.py:78`). Async on the I/O path; sync where correct. |
| Real error handling, validation, observability — not happy-path | 3 | Three exception handlers (`HolofyError`, `RequestValidationError`, catch-all) all render the one envelope; 500 logs server-side and never leaks internals (`main.py:87`). Typed `HolofyError` hierarchy with stable `code`s. Structured JSON logging with context-var request-id threaded through async stages. Input validation via `Field(min_length=1, ge=1)`. |
| Tests: unit + integration, green | 3 | 27 green, layered (provider unit, service unit, API integration via TestClient). Hermetic. Cover failure branches, not just happy path. |
| No secrets in code; EU residency & GDPR primitives respected | 3 | Zero secrets/keys in code (grep clean); TCGdex is keyless by design. `data_region` pinned `eu-central-1`, surfaced on `/health` so region drift is observable. `.env` gitignored. CORS deny-by-default. |

**Lens avg: 3.0 — every criterion ≥2. PASS.**

Backend findings (non-blocking):
- **B1 (low):** `factory.py:21` and `:35` `match` blocks have no `case _` fallthrough. Every
  enum member is currently covered, so no live bug — but if a future backend enum value is
  added without a branch, the builder returns `None` implicitly instead of raising. Add an
  exhaustiveness guard (`case _: raise ...`) to fail loud.
- **B2 (trivial):** `tcgdex.py:151` docstring says "`httpx.HTTPError` propagates for the
  latter," where "the latter" grammatically points at the no-pricing case (which actually
  raises `PriceUnavailable`). Wording nit; the code is correct.
- **B3 (low):** `PriceQuote.value` is `Decimal | None` and `_to_quote` can emit `value=None`
  when both `trend` and `avg30` are absent but `cardmarket` block exists (e.g. only `low`).
  The service tolerates this (`_price_delta` null-guards), and the UI contract allows null
  price, so this is intentional and safe — noted for completeness.

---

## Lens 3 — Security & Privacy (§3.5)

| Criterion | Score | Notes |
|---|---|---|
| Authz on every user-data path; signed expiring URLs for images | 2 | **No authz exists** — `/scan` is unauthenticated. This is **reasonably deferred**: the slice handles no per-user data (no portfolio, no user-owned images; capture bundles are opaque refs with no ownership model yet). Auth lands with the portfolio write in P1.4. Scored 2 (not 3) because there is also no placeholder/marker reserving the authz seam — a fresh builder could wire P1.4 forgetting it. No fake/stub auth was shipped, which is the correct choice over a tutorial-grade decorator. |
| Explicit, revocable consent for training data; erasure propagates | 2 | No training-data capture in this slice (data lake is Phase 3). Nothing collected, nothing to consent to — correctly out of scope, no violation. Cannot score 3 as there's nothing to evaluate positively yet. |
| Rate-limit / quota enforced | 2 | **Not implemented.** Defensible at the skeleton stage (gateway-level rate-limit per architecture §6, plus RevenueCat quota tiers, are infra/Product-owned and Phase-1-billing scope). But `/scan` is the COGS-bearing endpoint, and there is no marker/middleware seam reserved for it. Reasonably deferred, flagged as the **highest-priority pre-exposure gap**. |
| Anti-fake never a binary public "FAKE" verdict | 3 | N/A to this slice (no anti-fake here) — and the error model is private-by-design: 500s never leak internals, details carry only non-sensitive context (`canonical_id`, `bundle_id`). No defamation surface introduced. |

**Lens avg: 2.25 — every criterion ≥2, but avg < 2.5. Lens does NOT meet the ≥2.5 average bar.**

Security findings:
- **S1 (high, before any public exposure):** No rate-limit/quota on `/scan`, the endpoint
  that will drive paid recognition/pricing COGS. Acceptable for a keyless mock skeleton;
  must be a tracked gate before this endpoint hits a real provider in a deployed env.
- **S2 (med):** No authz on `/scan` and no reserved seam (dependency stub / `# TODO authz`
  marker) for it. Correct to not ship fake auth, but the absence of any placeholder risks a
  silent gap when P1.4 adds user data. File a follow-up to introduce the auth dependency
  with the portfolio write.
- **S3 (low):** `CORSMiddleware` uses `allow_credentials=True` with `allow_methods=["*"]` /
  `allow_headers=["*"]`. With `allow_origins` deny-by-default this is safe today, but
  `*`-methods/headers alongside credentials is a habit worth tightening to the actual
  surface (`POST`, `Content-Type`, `X-Request-ID`) before production.

**Note on scoring:** every criterion is ≥2 (deferrals are honest and no insecure code was
shipped), but the lens average (2.25) falls below the §3 0.5 threshold because three of the
four criteria are "nothing to evaluate / deferred" rather than positively demonstrated. By
the letter of §3 this lens does not PASS. This is a **scope artifact, not a defect** —
there is no security *regression* in the slice; the deferred items (authz, quota, consent)
genuinely belong to later slices. Recommend the orchestrator treat the security lens as
**CONDITIONAL PASS** contingent on S1/S2 being filed as gating follow-ups for P1.4, OR
formally mark security N/A-deferred for P1.1 in STATUS. As scored against the raw rubric:
**FAIL on the ≥2.5 average rule.**

---

## Lens 4 — Premium / Not-Generic gate (§3.6)

AI-tell scan:

- **Over-commenting / narrating the obvious:** None. Comments explain *why*, not *what*
  (e.g. "round-trip through str so we don't inherit binary-float noise on money",
  "deny-by-default so a forgotten wildcard can't leak the API"). Module docstrings carry
  intent and architecture references, not restatements of the code.
- **Speculative abstraction / dead code / unused params:** None found. Protocols are used,
  the factory's returned client is genuinely consumed by lifespan shutdown, no orphan
  helpers. `CaptureBundle` Protocol is justified (storage shape will evolve).
- **Generic naming:** Absent. Domain-precise throughout: `CardmarketPrice`, `display_value`,
  `needs_confirmation`, `price_delta`, `canonical_id`, `confirm_threshold`. No `handleData`/
  `foo`/`temp`/`utils`.
- **Copy-paste drift:** The spike→production consolidation is a real refactor, not a paste
  (verified by diff). No duplicated logic across files.
- **Boilerplate README / hype copy / emoji:** README is precise and domain-specific (mocked-
  vs-real table, exact run commands, config table). No marketing voice, no em-dash soup, no
  decorative emoji.
- **House style consistency:** Uniform — `from __future__ import annotations`, frozen
  pydantic configs, module docstring + why-comments, consistent error/DTO patterns across
  every file. No mixed conventions.
- **Unglamorous polish present:** request-id correlation echoed on errors too, 500s scrubbed
  of internals, `Decimal` money discipline, deterministic `as_of` for testable freshness,
  the low-confidence case as the *default* fixture so the hard path is what you hit.

**Zero AI-tells. Every criterion ≥2 (lenses above). Premium gate: PASS.** This reads as
work a senior backend engineer at a product studio would ship: restraint, taste, domain
fluency, and the boring details done right.

---

## Verdicts

| Lens | Avg | Min criterion | Verdict |
|---|---|---|---|
| Architecture (§3.2) | 2.75 | 2 | **PASS** |
| Backend (§3.3) | 3.00 | 3 | **PASS** |
| Security & Privacy (§3.5) | 2.25 | 2 | **FAIL** (avg < 2.5; deferral-driven, see note) |
| Premium (§3.6) | — | ≥2, zero AI-tells | **PASS** |

## Prioritized findings

1. **S1 (high):** Add rate-limit/quota on `/scan` before it fronts a real provider in any
   deployed environment. (`app/api/scan.py:19`)
2. **S2 (med):** Introduce an auth dependency + reserve the authz seam when P1.4 adds
   user/portfolio data; do not let the current no-auth skeleton become the merged baseline
   silently. (`app/api/scan.py`, `app/api/dependencies.py`)
3. **B1 (low):** Add `case _: raise` exhaustiveness guards in the factory. (`app/providers/factory.py:21,35`)
4. **S3 (low):** Tighten CORS `allow_methods`/`allow_headers` to the real surface before
   production given `allow_credentials=True`. (`app/main.py:107`)
5. **B2 (trivial):** Fix the "the latter" docstring referent. (`app/providers/pricing/tcgdex.py:151`)

## Recommendation to orchestrator

Architecture, Backend, and Premium PASS cleanly — this is high-quality, premium-bar work.
The Security lens FAILs only on the §3 average rule, driven entirely by deferred-scope
criteria (authz/quota/consent belong to later slices) rather than any insecure code; no
security regression was introduced. **Gate this slice as PASS conditional on S1 and S2
being filed as explicit gating follow-ups for P1.4**, and record in STATUS that the
security lens is scoped-deferred for the P1.1 mock skeleton. Do not require a refine cycle
on the security lens for this slice — there is nothing to fix here, only to schedule.
