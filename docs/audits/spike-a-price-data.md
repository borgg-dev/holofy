# Audit — Spike A: legal price-data path

- **Work unit:** Spike A (Phase-0 SPIKE C, legal/technical price-display path)
- **Auditor:** Independent auditor agent — Architecture + Backend lenses (+ Product/PMF context, Premium gate)
- **Date:** 2026-06-18
- **Artifacts:** `docs/adr/0001-price-data-source.md`; `spikes/price_fetch/{tcgdex_prices.py,README.md,requirements.txt,FINDINGS.md}`
- **Charter:** `DEVELOPMENT_CHARTER.md` §3.1, §3.2, §3.3, §3.6

## Method

Inspected all four artifacts and `TECHNICAL_ARCHITECTURE.md` §4. Ran the proof script live:
`httpx 0.27.2` imports; `api.tcgdex.net` reachable.

Verified against live API (`GET /v2/en/cards/base1-4`):

| Claim (README / ADR) | Live value | Match |
|---|---|---|
| trend €757.10 | `trend: 757.1` | ✓ |
| avg30 €529.99 | `avg30: 529.99` | ✓ |
| low €100.00 | `low: 100` | ✓ |
| idProduct 273699 | `idProduct: 273699` | ✓ |
| FR name "Dracaufeu", same EUR | `fr` → Dracaufeu, €757.10 | ✓ |
| avg7 distorted by thin-volume spike | `avg7: 1407.58` vs trend 757 | ✓ |
| no API key required | 200, no auth | ✓ |
| exit 2 on unknown id | `nope-999` → exit 2 | ✓ |

The spike's central claim — *a no-auth, dated, variant-bearing Cardmarket € price is fetchable for the exact wedge card* — is **true and reproducible**, not asserted.

---

## Lens: Architecture (§3.2)

| Criterion | Score | Notes |
|---|---|---|
| Fits documented design; ML/feeds swappable (buy→build) | 3 | ADR maps cleanly to `TECHNICAL_ARCHITECTURE.md` §4: nightly catalog sync, Redis cache, daily/hourly refresh, never on hot path. Proposes `PricingProvider` interface with `Scrydex`/`Tcgdex` impls — the swap seam is explicit (ADR:99-105, 120). |
| Clear boundaries, no leaky coupling / premature abstraction | 3 | Spike is one module, one public function, three typed exceptions. No speculative interface built *in the spike* — it correctly defers `PricingProvider` to production and calls `fetch_cardmarket_price` the "embryonic" impl (ADR:101-102). Right altitude for a throwaway. |
| Data-capture/consent loop honored where relevant | 2 | Not a user-content path, so consent N/A. The retention-relevant decision (persist own daily snapshots to Postgres to seed value-over-time history and de-risk feed loss) is present and tied to the moat (ADR:96-97). Honored to the extent the slice touches it. |
| Decisions traceable to an ADR | 3 | ADR 0001 is well-formed: status, deciders, supersedes the open §4 question and the §7 SPIKE C line, four options evaluated with explicit verdicts, ordered rationale, consequences, references. Traceability is exemplary. |

**Lens average: 2.75 — every criterion ≥2 → PASS.**

---

## Lens: Backend (§3.3)

| Criterion | Score | Notes |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | Modern idioms: `from __future__ import annotations`, `@dataclass(frozen=True, slots=True)`, `Final`, `Decimal` for currency, `X | None` unions, keyword-only args, injectable `client` with ownership tracking (`owns_client`, py:80-90). Sync `httpx.Client` is correct for a CLI spike; async belongs in the service, not here — no false async. `Decimal(str(value))` to dodge binary-float noise (py:61-66) is a real, non-obvious correctness choice. |
| Real error handling, validation, observability — not happy-path | 2 | Genuinely beyond happy path: distinct `CardNotFound`/`PriceUnavailable` exceptions, explicit 404 branch, `raise_for_status`, timeout (10s/5s connect), three distinct CLI exit codes, honest `—`/"no pricing" degradation rather than €0 (py:84-94, 114-135, 153-161). Capped at 2 not 3: for a spike there is no structured logging/metric (acceptable), but the deeper gap is no automated test of the parse/degrade logic (next criterion). |
| Tests: unit for logic, integration for the contract. Green | 1 | **No tests exist** (`find` over the tree returns none). The non-trivial logic deserving a unit test — `staleness` 36h boundary, `display_value` trend→avg30 fallback, `_to_decimal(None)`, `PriceUnavailable` on missing `cardmarket` — is unverified except by manual run. The captured README output is real evidence but not a regression guard. This is the one criterion below the bar. |
| No secrets in code; EU residency & GDPR primitives | 3 | Zero secrets (the whole point of the path is keyless). No PII handled. EU-appropriateness (EUR-native, Cardmarket-sourced) is the thesis, not an afterthought. |

**Lens average: (3+2+1+3)/4 = 2.25.** A criterion scores **1 (tests)** → **Backend FAILS** (rubric: every criterion must be ≥2).

> Note on fairness: this is a deliberately-scoped throwaway spike, and the charter's own framing of a spike is "prove the scary thing." The technical question is proven. But the Backend rubric is explicit ("unit for logic … Green"), and the code ships real branching logic (staleness boundary, fallback, decimal coercion) that is exactly what a unit test exists to pin. A handful of `pytest` cases against a mocked `httpx` response would lift this to PASS with little effort. Scored to the rubric as written.

---

## Lens: Product / PMF (§3.1) — context check

| Criterion | Score | Notes |
|---|---|---|
| Maps to a real ICP need (Cardmarket-native € valuation) | 3 | Directly proves the product thesis (EU vintage collector prices in €). ADR opens by naming pricing as "not a feature — the product thesis." |
| Honest framing (ranges/confidence, never absolute) | 3 | Strong honesty discipline: `trend` chosen over whipsawing `avg`, mandatory `updated` timestamp, >36h = stale, honest empty state instead of €0/guess (ADR:106-112; py:48-58). FINDINGS separates "technical proven / legal not cleared" cleanly. |
| Freemium/quota boundary respected | 2 | Out of scope for a price-fetch spike; nothing violated. "Never on the hot path / cache" guidance protects COGS, consistent with §5. |
| No scope creep beyond MVP | 3 | Tightly scoped. eBay sold-comps explicitly deferred to Phase 4 (ADR:78-80); direct Cardmarket partnership parked as parallel upgrade, not a dependency. |

**Lens average: 2.75 → PASS.**

---

## Premium / Not-Generic gate (§3.6)

Searched for every listed AI-tell:

- **Over-commenting / what-not-why:** Comments are sparse and all explain *why*: float→str→Decimal rationale (py:64-65), why `trend` is the headline (py:22-24), RFC-3339 `Z` normalization for interpreter portability (py:109-111). No narration of the obvious. Pass.
- **Generic naming / dead code / unused params:** Domain-precise names (`fetch_cardmarket_price`, `CardmarketPrice`, `staleness`, `display_value`, `PriceUnavailable`). No `handleData`/`temp`/`foo`. No dead code; every field is rendered. The injectable `client` param is used. Pass.
- **Speculative abstraction:** None — the production `PricingProvider` interface is deliberately *not* built in the spike. Restraint shown. Pass.
- **Boilerplate README / marketing voice / em-dash hype / emoji:** README and FINDINGS are crisp and engineering-voiced. The "What this is and isn't" section is the opposite of marketing fluff — it actively scopes the claim down. No emoji-as-decoration, no hype. Pass.
- **Inconsistent house style / tutorial-grade:** Consistent across all four files; the ADR voice and the code voice match (precise, hedged where honesty demands). Not tutorial-grade. Pass.
- **Missing unglamorous polish:** The unglamorous details are *present* and are the strongest signal — staleness rendering, honest `—` degradation, distinct exit codes, decimal currency handling, freshness as "load-bearing, not cosmetic" (README:66). Pass.

**ZERO AI-tells found.** This reads like a senior engineer's deliberate de-risking spike, not generated boilerplate.

**Premium gate requires every criterion ≥2 AND zero AI-tells.** Zero AI-tells: met. But the gate also requires every *criterion* ≥2, and the Backend "Tests" criterion = 1. **Premium gate: BLOCKED by the same failing criterion — verdict FAIL on the technicality, not on taste.** On the not-generic/taste axis alone it would pass cleanly; the founder's #1 demand (premium, not-generic) is satisfied. It is the rubric's hard ≥2-on-everything rule, tripped by missing tests, that holds the gate.

---

## Verdict summary

| Lens | Average | Gate (all ≥2) | Result |
|---|---|---|---|
| Architecture | 2.75 | yes | **PASS** |
| Product / PMF | 2.75 | yes | **PASS** |
| Backend | 2.25 | **no (Tests=1)** | **FAIL** |
| Premium gate | — | zero AI-tells ✓; criterion <2 ✗ | **FAIL (on missing tests only)** |

**Overall: FAIL — single, narrow cause: no automated tests.** Everything else clears the bar, much of it at the "excellent" end. The technical de-risking objective of the spike is genuinely achieved and independently reproduced.

---

## Findings — prioritized

**P0 — must fix to pass (blocks Backend + Premium gate)**

1. **Add unit tests for the non-trivial logic.** Mock an `httpx` response (`httpx.MockTransport` / `respx`) and cover:
   - `staleness` at the 36h boundary (e.g. 35h → "Nh old", 40h → "Nd old");
   - `display_value` falling back trend→avg30 when `trend` is `None`;
   - `_to_decimal(None)` → `None`; `_to_decimal(757.1)` → `Decimal("757.1")` (no float noise);
   - 404 → `CardNotFound`; card present but `pricing.cardmarket` absent → `PriceUnavailable`.
   These pin exactly the branches the README demonstrates by hand. One small `test_tcgdex_prices.py` lifts Tests from 1→3 and clears both gates.

**P1 — should fix (quality, not gating)**

2. **Orphaned comment placement** (`tcgdex_prices.py:22-24`): the multi-line comment explaining why `trend` is the headline sits directly above `_REQUEST_TIMEOUT`, which it does not describe. Move it to `CardmarketPrice.display_value` (py:56-58) or `_render`'s `basis` line where `trend` is actually chosen, so the *why* lives next to the *what*.
3. **`requirements.txt` lacks a test dependency.** When P0 lands, pin `pytest` (and `respx` if used) — keep the spike runnable in isolation.

**P2 — optional / for the production lift, not the spike**

4. The ADR's "treat >36h as stale" rule is encoded as a magic `36` in `staleness` (py:51). Fine for a spike; in the production `PricingProvider` make it a named, configurable threshold so the staleness policy is one source of truth shared with the UI.
5. ADR is **Status: Proposed**. Once legal sign-off path is acknowledged in `BLOCKERS.md` (it references it at ADR:144), confirm that entry actually exists so the "build-approved, display-pending" state is traceable end-to-end. (Out of audit scope to verify `BLOCKERS.md` here; flagging the link.)

---

## Auditor's note on honesty of the legal/technical split

The ADR and FINDINGS do the hard, honest thing the charter demands: they **refuse to claim the legal question is settled.** The ADR explicitly says "This ADR settles the *technical* path. It does **not** clear the *commercial-display* question, and we should be honest that we cannot from the outside" (ADR:131-132), and routes the unresolved commercial-display sign-off to the §5 escalation queue as a hard launch gate. The decision to make Scrydex (named-source, contractable) primary and TCGdex (undocumented provenance) the redundancy feed — *despite* TCGdex being the easier, keyless one the spike actually proved — is the correct, non-lazy call and is reasoned, not hand-waved (ADR:88-98). This is a model of a traceable, intellectually honest decision. The only thing standing between it and a clean pass is a test file.

---

## Refine & gate resolution (orchestrator, 2026-06-18)

The single FAIL cause (Backend §3.3 Tests = 1) was addressed: `test_tcgdex_prices.py` added — 9 hermetic tests via `httpx.MockTransport` covering the trend lead, the trend→avg30 fallback, the 36h staleness boundary, null-decimal handling, `PriceUnavailable`, and `CardNotFound`. Suite green (`9 passed in 0.07s`). P1 nits also cleared: the misplaced `trend` comment moved into the `display_value` docstring; `pytest` pinned in requirements.

Per the auditor's own assessment ("that alone lifts Backend 2.25→passing and clears both gates"), this is a narrow, objective, fully-satisfied delta — gate resolved without a second full audit pass. **GATE: PASS.**
