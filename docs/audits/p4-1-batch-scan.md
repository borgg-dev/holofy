# P4.1 Audit — Batch / Stack Scan (architecture §3.2 · backend §3.3 · security/privacy §3.5 · Premium §3.6)

**Auditor:** independent (architecture · backend · security/privacy · §3.6 Premium gate). Did not build this; audited adversarially.
**Date:** 2026-06-18
**Artifacts:** `apps/api/app/api/batch_scan.py`, `app/services/batch_scan.py`, `app/schemas/batch_scan.py`, `app/services/scan.py` (`classify()` / `ScanClassification` factoring), `app/providers/recognition/mock.py` (fixtures), `tests/test_batch_scan.py`, `scripts/smoke_journey.py` (stack step), `README.md`.

## Verdict

**FAIL.** Security/Privacy §3.5 fails on its single most important criterion — the quota is **not COGS-safe**. Recognition (the ~$0.01/scan cost lever, architecture §3.1/§5.3) is spent in Pass 1 on **every** raw capture *before* the quota gate in Pass 2, so a user with zero remaining daily budget can still drive up to 50 recognition calls per request, with **no per-request or per-day cap on the number of batch requests**. The single `/scan` charges quota *before* recognition for exactly this reason (`api/scan.py:43`); the batch path inverts that order. A second defect: dedupe namespaces the merge key by *outcome* (`resolved:` vs `confirm:`), so one physical card whose confidence straddles the threshold across two flips fails to collapse and is **charged twice**. The shared-`classify()` factoring itself is genuinely clean and well-documented; the failures are in the batch service's ordering and key design, not the refactor.

### Build / verify gates (all green, captured)
- `PYTHONPATH=.deps:. .deps/bin/pytest -q` → **169 passed** in 3.53s.
- `PYTHONPATH=.deps:. python3 -m alembic check` → **No new upgrade operations detected** (no drift).
- `bash scripts/dev_smoke.sh` → full live journey green incl. the stack step: `scan (stack) : 3 card(s) [resolved×2, resolved×1, unrecognized×1] · charged 2/8 · 4 left`.
- Single-scan regression: `pytest -k "scan and not batch"` → **22 passed** — `classify()` extraction did not change single-scan behavior.

---

## Falsification attempts

### COGS-safety — FAILS (the most important gate) — Finding 1
The README ("two axes … the `max=50` batch cap bounds the recognition calls one request can trigger") and the schema docstring (`batch_scan.py:48` "skipped before recognition") and the service docstring (`services/batch_scan.py:18-19` "neither persisted nor banked … no COGS spent") all imply recognition spend is bounded by quota. It is not.

`scan_batch` (`services/batch_scan.py:92-103`) runs `await self._scan.classify(bundle)` — which calls `recognition.recognize()` — for **every** item in Pass 1, unconditionally. The limiter is only consulted in Pass 2 (`:112`), and only gates **persistence/banking**, not recognition.

I proved it empirically: with the daily budget of 8 fully exhausted (`remaining=0`), a single 50-item batch produced **50 recognition calls** and `charged=0`. Every one of those 50 calls is a real Ximilar credit in production. The `quota_exceeded` items truthfully report `charged=0`, but the COGS was already spent — the response is honest about *banking* while silently spending *recognition*, which is the exact cost the §5.3 control ("on-device pre-filter so only … cards hit the cloud; plan quotas") exists to bound.

Worse, there is **no per-request rate limit on the batch endpoint** (`api/batch_scan.py` calls the limiter zero times; `main.py` registers only CORS + request-id middleware). The `MAX_BATCH_ITEMS=50` cap bounds spend *per request* but a user may fire unlimited batch requests, so daily recognition COGS for a free-tier user is effectively **unbounded**. This directly violates §3.5 ("Rate-limit/quota enforced — protects COGS") and the architecture's named control. **P0.**

### Dedupe correctness — one real defect — Finding 2
- Same card flipped twice, both confident → collapses to one item, `count=2`, charged once. ✓ (`test_dedupe_collapses_repeats_into_one_result_with_count`).
- Two low-confidence reads of the same top candidate → collapse to one `needs_confirmation`, `count=2`, charged once. ✓ (`test_low_confidence_repeats_dedupe_on_top_candidate`).
- Different cards stay separate; unrecognized never dedupe (each its own item). ✓.
- **Defect:** the dedupe key is `f"resolved:{id}"` (`scan.py:121`) vs `f"confirm:{id}"` (`scan.py:108`) — namespaced by *outcome*, not identity. One physical card whose recognition confidence lands at 0.90 on one flip (resolved) and 0.80 on another (needs_confirmation, threshold 0.85) gets two distinct keys and does **not** collapse. I reproduced it: two flips of one card → **2 items** (`resolved` + `needs_confirmation`), **charged 2**. This is the precise "two reads of the same top candidate" failure the audit brief asked me to construct, and it breaks the headline promise ("charged once per distinct card", "a re-flip costs nothing"). Frame-to-frame confidence jitter around the threshold is the common case, not a corner. **P1.**

### Persistence + consent — holds
- One `ScanRecord` per *distinct accepted* card, `capture_ref` = first flip (`services/batch_scan.py:177-186`); merged flips are quantity, not events. ✓ (`test_dedupe…` asserts 2 records for 4 flips).
- Consent off by default → nothing reaches the lake (`test_consent_off_by_default_nothing_reaches_the_lake`). Consented → exactly one example per deduped card, not per flip (`test_consented_batch_emits_one_example_per_deduped_card`). The emit gate is the same single `emit_scan` hard line as single-scan. ✓.
- Endpoint correctly refuses a per-request opt-in for stack mode and resolves standing account consent (`api/batch_scan.py:46-48`) — a deliberate, defensible choice. ✓.

### Validation / auth — holds
- Empty batch → 422 (`min_length=1`), oversized → 422 (`max_length=50`); auth required → 401 with `not_authenticated` envelope. All three covered by tests and pass.

### Shared path — holds (the refactor is the strong part)
- Single `/scan` and batch both go through `ScanService.classify()`; the confirm threshold lives in exactly one place (`scan.py:100`, `result.needs_confirmation(self._confirm_threshold)`). No copy-paste of the recognize→price→confirm logic. `_upsert_card` is shared, not re-implemented. Single-scan behavior unchanged (22 tests green). This part is genuinely well done.

### Minor — Finding 3 (P3)
A `quota_exceeded` item hardcodes `count=1` and `capture_refs=acc.capture_refs[:1]` (`services/batch_scan.py:122-123`), discarding the real merged count/refs for a card that was deduped before being rejected. The schema comment (`schemas/batch_scan.py:62`) claims "a quota_exceeded … item is always one capture" — but a card flipped 3× then rejected genuinely merged 3 captures; the response under-reports it. Cosmetic (the card isn't banked), but the field is then dishonest about what the user flipped.

---

## Per-criterion scores

### Architecture §3.2 — PASS (avg 2.75)
| Criterion | Score | Note |
|---|---|---|
| Fits documented design; ML stages swappable | 3 | Reuses `classify()`/providers behind Protocols; stack mode matches arch §3.1. |
| Module boundaries, no leaky coupling, no premature abstraction | 3 | Endpoint thin; dedupe/quota/persist in service; `_Accumulator` is a tidy, non-speculative seam. |
| Data-capture/consent loop honored | 3 | One emit gate, per-deduped-card example, standing-consent resolution. |
| Decisions traceable to ADR | 2 | Confirm rule cites ADR 0002; the batch quota *ordering* decision (recognize-then-gate) is undocumented and, per Finding 1, wrong. |

### Backend §3.3 — PASS (avg 2.5)
| Criterion | Score | Note |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async | 3 | Clean async, dataclasses, `StrEnum`, full typing. |
| Real error handling / validation / observability | 2 | 422/401/partial-acceptance all real; but the `quota_exceeded` `count` truncation (Finding 3) is a correctness gap in the response contract. |
| Tests: unit + integration, green | 3 | 169 green; the batch suite covers dedupe, partial quota, consent, auth. (Gap: no test for the cross-outcome dedupe split — Finding 2 — which is why it shipped.) |
| No secrets; EU/GDPR primitives | 2 | Consent path correct; no secrets. |

### Security & Privacy §3.5 — **FAIL** (avg 2.0; COGS criterion = 1)
| Criterion | Score | Note |
|---|---|---|
| Authz on every user-data path; signed URLs | 3 | `get_current_user` gates the route; user-scoped persistence and quota key. |
| Explicit, revocable consent for training use | 3 | Standing account consent; emit gate honors revocation; off by default. |
| **Rate-limit/quota enforced (protects COGS)** | **1** | Recognition spent before the gate; no per-request/day batch cap → unbounded recognition COGS (Finding 1). Banking is capped; the cost lever is not. |
| Anti-fake never a binary verdict | 3 | N/A — batch is ID+value only; no authenticity output. |

A criterion at 1 auto-fails the lens (every criterion must be ≥2).

### Premium / Not-Generic §3.6 — **FAIL** (gate)
Zero stylistic AI-tells: naming is domain-precise (`_Accumulator`, `dedupe_key`, `quota`), docstrings explain *why* not *what*, house style matches the single-scan files, no dead code, no copy-paste (the refactor is the opposite of drift). On craft alone this would pass.

**But §3.6 requires every criterion ≥2, and it fails on substance, not style:** the README/docstrings *advertise* COGS-safety ("no COGS spent", "a batch can't bypass the cap", "two axes" guarding cost) that the implementation does **not** deliver — the recognition spend escapes the gate. A top-tier studio would not ship a quota whose own documentation overstates the protection it provides, and the threshold-straddle double-charge is exactly the "missing edge case" the gate calls out. **Auto-FAIL** until Findings 1 and 2 are fixed.

---

## Prioritized findings

- **P0 — Finding 1 (COGS bypass).** `services/batch_scan.py:92-103` runs recognition on all items before the Pass-2 quota gate (`:112`); `api/batch_scan.py` adds no per-request rate limit; `main.py` no global one. A zero-budget user drives ≤50 recognition calls/request, unlimited requests/day. Fix direction: gate recognition spend itself — e.g. reserve budget *before* `classify()` (charge dedupe-after by reconciling), or add a per-request batch-submission limit on the same daily key, so recognition calls are bounded by the free-tier budget the way `/scan` already bounds them. Correct the README "no COGS spent" / "two axes" claims to match whatever the real bound is.
- **P1 — Finding 2 (cross-outcome dedupe split → double charge).** `scan.py:108` & `:121` namespace `dedupe_key` by outcome. Same card across the confirm threshold on different flips → two items, charged twice. Fix direction: key dedupe on the resolved canonical id alone (`f"{canonical_id}"`), and decide the merged outcome deterministically (e.g. any confident read wins). Add a test for the threshold-straddle case.
- **P3 — Finding 3 (quota_exceeded count under-reports).** `services/batch_scan.py:122-123` drops the merged count/refs for a rejected-after-dedupe card; `schemas/batch_scan.py:62` comment asserts the false invariant. Carry the real `count`/`capture_refs` through or correct the comment.

## Recommendation
REFINE. The slice is well-built stylistically and the shared-`classify()` factoring is exactly right, but it fails the §3.5 COGS gate (P0) and the §3.6 Premium gate, and carries a real double-charge dedupe bug (P1). Feed Findings 1–2 back to the builder; re-audit.

---
## Refine & gate resolution (orchestrator, 2026-06-18)
Both FAIL findings fixed and independently verified:
- **P0 (COGS bypass):** batch now charges-before-recognize per capture in submission order (batch_scan.py:99 check_and_consume precedes :108 classify); a budget-exhausted capture is appended to `exhausted` and never reaches the recognizer. Recognition calls ≤ remaining budget by construction. The auditor's exact falsification is now a passing test (`test_exhausted_budget_drives_zero_recognitions`: 50-item batch, budget=0 → recognizer called 0×). `test_partial_budget_bounds_recognitions_to_remaining` (3 left → exactly 3 calls) added.
- **P1 (dedupe):** dedupe key is now identity-only (canonical_id), threshold-agnostic — a resolved+needs_confirmation straddle of one card collapses to one item (`test_threshold_straddle_collapses_across_outcomes`). Dedupe affects banking/display only, not refunds.
- **P3:** quota_exceeded carries the real capture count; README rewritten honestly (per-capture credit; re-flip-is-free claim removed).
Verified: 170 tests (single-scan unchanged at 22), alembic clean, live smoke green ("charged 4/8 · 2 left"). **GATE: PASS — merged.**
