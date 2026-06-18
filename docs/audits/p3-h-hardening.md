# P3.H Audit — Hardening Pass (backend + security/privacy + architecture + §3.6 + mobile bits)

**Auditor:** independent (backend · security/privacy §3.5 · architecture §3.2 · Premium §3.6 · design for the mobile consent/tabular bits). Did not build this.
**Date:** 2026-06-18
**Artifacts:** `apps/api` (schemas/authenticity.py, providers/authenticity/mock.py, services/authenticity.py, main.py, db/repositories/_flush.py + the 8 write repos, core/errors.py, migrations/…f7c6cff46e4c, api/authenticity.py, api/pregrade.py) + `apps/mobile` (src/screens/privacy/consent.ts + tests, src/screens/authenticity/VerdictScreen.tsx)

## Verdict

**PASS — all lenses pass; Premium gate PASS (zero AI-tells).** The defamation contract is genuinely closed at the type level and the ban-list test is real, not theatre. One **P2 finding** (CORS omits `PUT`, which the consent endpoint actually serves — contradicts the change's own stated contract) and two P3 notes; none gate the slice, but the CORS one should be fixed because it's the exact claim the change advertises.

### Build/verify gates (all green, captured)
- `pytest -q` → **159 passed** in 3.08s.
- `alembic upgrade head` → clean through `f7c6cff46e4c`; `alembic check` → **No new upgrade operations detected** (no drift).
- `bash scripts/dev_smoke.sh` → full live journey green; `authenticity : strong_signals · evidence conf 0.922 · recommend_authentication=True (risk flag, no verdict)`; `consent : granted=True (account-level)`.
- mobile `npm test` → **112 / 112 pass**; `npx tsc --noEmit` → **exit 0**.

---

## Falsification attempts (tried hard to break each)

### Defamation contract — HOLDS (the most important gate)
- `SignalDetail` (`schemas/authenticity.py:64-115`) is a `StrEnum` of **16 members** (prompt said "15" — harmless miscount; every member is clean). I enumerated all members in-process: word-boundary-matched against 13 accusatory tokens (`fake/faked/counterfeit/genuine/authentic/real/replica/bootleg/knockoff/knock-off/forgery/forged/fraud`) → **zero hits**. The only `authentic` substring is inside "professional authentication" (the honest next-step phrasing), which the word-boundary filter correctly passes. No member asserts a card is fake/genuine; the most adverse phrasing is "differs from the reference — worth a closer look by a professional" / "worth professional authentication."
- The ban-list test is **real, not theatre** (`tests/test_authenticity_provider.py:87-114`): it iterates every enum member with `re.search(\b…\b)` over all 13 tokens, **and** a structural test asserts pydantic `ValidationError` when free text (`"This card is a counterfeit."`) is passed to `AuthenticitySignal.detail`.
- **No free-text path remains.** `detail` is typed `SignalDetail` on the model (`:160`). The mock provider can only *select* members (`mock.py:114-121`). The service's catalog signal also selects from a closed `_CATALOG_OBSERVATION` map (`services/authenticity.py:162-175`). `_retake` interpolates `s.detail` into a reason string (`:287`) but the value is still an enum member — no constructible accusation. This directly closes prior **P3.2-F1** at the seam it flagged.
- No `is_fake`/`is_genuine` field anywhere; `RiskBand` remains the 3-band closed set (`:118-129`).

### CORS — mostly right, one real gap (Finding 1)
- Origins are **deny-by-default**: `cors_allow_origins: list[str] = Field(default_factory=list)` (`config.py:93`); the middleware passes that list verbatim (`main.py:151`).
- `allow_headers` = `Authorization, Content-Type, X-Request-ID` — exactly the headers the client sends/reads; `expose_headers` exposes the correlation header. Correct.
- `allow_methods=["GET","POST","OPTIONS"]` (`main.py:153`) but the routers serve **5×GET, 5×POST, and 1×PUT** — `PUT /consent/training` (`api/consent.py:37`). The change's own comment claims "the verbs the API actually serves"; `PUT` is omitted, so a *browser* client toggling consent would get its preflight rejected. RN/mobile and the smoke client aren't CORS-bound, so tests stay green. **P2** — see Finding 1.

### Migration — clean, no unintended change
- `f7c6cff46e4c` (`migrations/versions/20260618_1508-…`) drops only `ix_price_observations_card_id` via `batch_alter_table` (Postgres-safe); `downgrade` recreates it. The composite `ix_price_observations_card_id_observed_at` is untouched (`models/price.py:48`), and the model already documents the absence of the standalone index (`price.py:53-54`) — so `alembic check` finds no drift, as confirmed.

### Error mapping — typed 409, session unpoisoned
- `flush_or_conflict` (`_flush.py:19-32`) catches `IntegrityError`, **rolls back**, then raises `ConstraintViolationError` (409, `core/errors.py:84-94`). Wired into **all 8 write repositories** (user, pregrade, collection, scan, card, price, authenticity). `_constraint_detail` exposes only the driver constraint name, never the raw SQL.
- Test `test_duplicate_price_snapshot_is_rejected` (`test_persistence.py:279-298`) and `test_duplicate_collection_item_maps_to_a_domain_conflict` (`:371-389`) drive a real duplicate insert **through the repo** and assert `status_code == 409` / `code == "constraint_violation"` — not a 500. (Minor: neither test asserts the session is usable *after* rollback by doing a follow-up write — the rollback exists and is exercised, but the "not poisoned" property isn't locked by a test. P3, Finding 2.)

### No regressions on the prior hard lines
- **Privacy zero-emission:** `emit.py:36-37` short-circuits a non-consented/revoked record to a no-op before the sink is touched (`_is_consented`, `:31`). Intact.
- **Consent inheritance:** `/authenticity` resolves account-level standing consent, never the wire flag in isolation (`api/authenticity.py:137-141`). Intact.
- **Honest framing / no-verdict:** band-not-boolean, value-gate, refuse-over-guess all unchanged in `services/authenticity.py`. Smoke confirms `recommend_authentication=True (risk flag, no verdict)`.

### image_count threading — real, not cosmetic
- `/pregrade` (`api/pregrade.py:95`) and `/authenticity` (`api/authenticity.py:124`) both thread `request.image_count` into the capture object handed to the service/provider; the base capture types carry it (`providers/base.py:61,88`) and document why (holo needs multiple tilt angles). Defaults `=1, ge=1`.

### 429 quota — real
- `test_authenticity_free_tier_quota_returns_429_past_the_daily_limit` (`test_authenticity_api.py:173-199`) asserts the 9th screen → 429, `code=quota_exceeded`, `limit`, `reset_seconds>0`, **and** that the refused screen left no record. Quota is charged **before** any DB work (`api/authenticity.py:88-101`), so abuse can't drive COGS or persist. A second test proves the budget is shared with `/scan` (key `scan:{user_id}`).

### Mobile consent extraction + tabular figures
- `src/screens/privacy/consent.ts` is a clean pure-view-logic extraction (the 3 §3.5 rules: default-off, a11y-matches-value, equal-weight/no-dark-pattern), consumed by both `PrivacyScreen.tsx` and `FirstCapturePrompt.tsx` — no duplicated logic left behind. Tests in `__tests__/consent.test.ts` assert all three rules.
  - Naming nit: the prompt called these "render tests"; they are **logic** tests (node:test, no renderer — consistent with the repo's test stack). The trust rules are genuinely asserted; the label is just aspirational. Informational, not a finding.
- Tabular figures: `VerdictScreen.tsx:139` now passes `tabular` on the evidence-% caption (and `:194`) — closes prior **P3.2-F2**.

---

## Per-criterion scores

### §3.3 Backend — avg 2.75 (PASS)
| Criterion | Score | Note |
|---|---|---|
| Idiomatic FastAPI/Python, typed, async | **3** | `StrEnum` contract, typed `flush_or_conflict`, async throughout; no `type: ignore`/`any` papering in changed files (the one `# noqa: ANN001` is FastAPI's untyped `call_next`, pre-existing). |
| Real error handling/validation/observability | **3** | IntegrityError→typed 409 with rollback, wired into all 8 repos; quota→429 with reset metadata; request-id correlation intact. |
| Tests: unit + contract, green | **3** | 159 green; new ban-list (vocab + structural), 409 (2 repos), 429 (limit + shared-budget) tests are real and assert the right things. |
| No secrets / EU residency / GDPR | **2** | Unchanged & honored (data_region surfaced, consent gate upstream). Migration adds no PII surface. |

### §3.5 Security & Privacy — avg 2.75 (PASS)
| Criterion | Score | Note |
|---|---|---|
| No binary public FAKE verdict | **3** | Closed `SignalDetail` + ban-list test make an accusatory *sentence* structurally impossible, not just an accusatory band. Strongest hardening in this pass. |
| Authz / rate-limit / quota | **3** | `/authenticity` quota charged before DB; 429 test proves no-record-on-refuse + shared budget. |
| Consent revocable / erasure-aware | **3** | Zero-emission gate (`emit.py:36`) and account-level consent inheritance unchanged. |
| CORS / surface posture | **2** | Deny-by-default origins; headers exact. **−1: `allow_methods` omits the `PUT` the consent route serves** (Finding 1). |

### §3.2 Architecture — avg 2.75 (PASS)
| Criterion | Score | Note |
|---|---|---|
| Fits system design, ML stages swappable | **3** | `detail` closed at the *schema* seam, so the real CV ensemble inherits the defamation guarantee for free; provider Protocol unchanged. |
| Clear boundaries, no leaky coupling | **3** | `_flush.py` is a single shared helper; consent view-logic extracted to one module both UIs consume. No premature abstraction. |
| Data-capture/consent loop honored | **2** | Intact; gate centralized in `emit.py`. |
| Decisions traceable | **2** | Migration + schema docstrings explain *why* (redundant-prefix index, sentence-level defamation). No new ADR needed. |

### §3.6 Premium / Not-Generic gate — PASS (zero AI-tells, no veto)
No dead code, no `foo`/`temp`/`handleData`, no `any`/`ts-ignore`/`type: ignore` in changed files. Comments explain *why* (defamation at the sentence level, index-prefix redundancy, rollback rationale), never narrate the obvious. `SignalDetail` phrases are domain-precise and restrained ("worth a closer look by a professional", "a gap in our data, not a finding about the card"). House style consistent: `consent.ts` mirrors the authenticity `band.ts` view-logic split by design. **Would a top-tier studio ship this? Honest yes.**

---

## Prioritized findings

**Finding 1 (P2 — security/correctness; non-blocking but fix it):** CORS `allow_methods=["GET","POST","OPTIONS"]` (`apps/api/app/main.py:153`) omits `PUT`, but `PUT /consent/training` (`apps/api/app/api/consent.py:37`) is a real route. A browser client toggling training consent would have its preflight rejected. The change's own comment asserts these are "the verbs the API actually serves" — the gap contradicts the stated contract. Add `"PUT"`. (Didn't surface in tests/smoke because RN and the smoke client aren't CORS-bound.)

**Finding 2 (P3 — test coverage):** The 409 tests (`test_persistence.py:279-298`, `:371-389`) assert the typed conflict but never assert the session is usable *after* the rollback (e.g., a subsequent successful `record` on the same session). The rollback in `_flush.py:30` is correct and exercised; locking the "not poisoned" property with one follow-up write would make the guarantee regression-proof.

**Finding 3 (P3 — informational):** `consent.test.ts` is pure view-logic, not renderer-based render tests as the work item phrased it. Consistent with the repo's node:test-only stack and the rules are genuinely asserted — just a naming mismatch, no action needed.

---
## Gate resolution
PASS on all four lenses (every criterion ≥2, each avg ≥2.5) and Premium gate (zero AI-tells, no veto). Defamation contract is the headline win: closed enum + real ban-list test = no constructible accusatory `detail`. Prior P3.2-F1 (free-text detail) and F2 (tabular %) both closed. Ship; file Finding 1 (CORS PUT) as a quick follow-up.

---
## Gate resolution (orchestrator, 2026-06-18)
PASS all lenses + Premium gate. Defamation contract verified genuinely closed (SignalDetail enum, ban-list + structural tests) — closes P3.2-F1. Migration/error-mapping/429/image_count/CORS/consent-tests/tabular all verified; no regressions; live smoke green. The one real finding (P2: CORS omitted PUT while PUT /consent/training is live) FIXED — allow_methods now includes PUT; 159 tests + smoke still green. P3 notes (session-usable-post-rollback assertion, renderer-level consent tests) filed to #11. **GATE: PASS — merged.**
