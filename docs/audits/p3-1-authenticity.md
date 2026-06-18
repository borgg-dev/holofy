# Audit — P3.1 Authenticity (anti-fake) risk service

- **Slice:** P3.1 — authenticity / anti-fake risk-band service (`apps/api/`)
- **Auditor lenses:** Architecture · Backend · ML · Security/Privacy · Product/PMF (honest-framing) + §3.6 Premium gate
- **Date:** 2026-06-18
- **Builder report:** 130 passing — **verified** (130 passed in 2.28s).
- **Migration:** `alembic upgrade head` applies; `alembic check` → *No new upgrade operations detected* (no drift). **Verified.**

## Verdict

**ALL LENSES PASS. Premium gate PASS.** Ship.

This is a strong slice. The §3.5 defamation guardrail — the single most important criterion — is
**structural and falsification-resistant**: enforced in the schema, the ORM enum, a DB check
constraint, and the ADR, not in prose or UI copy. I tried to construct a binary/accusatory output
through the live service and could not.

---

## Hard-gate falsification (run against the live service)

| Probe | Expected | Observed | Result |
|---|---|---|---|
| Never-printed variant (`origins 12/120 1st_edition`) + **clean** visuals | floored at `elevated_risk` | `assessed / elevated_risk` (conf 0.922) | PASS — catalog floor is dispositive |
| Unverifiable (unknown base card) + clean visuals | NOT counted against | `strong_signals` | PASS — gap never accuses |
| Below value threshold (€5) | typed `not_assessed` | `not_assessed` | PASS — no fake-precise score |
| Unpriced (`None`) | `not_assessed` | `not_assessed` | PASS |
| Poor capture + unverifiable catalog | `retake` (200) | `retake` | PASS — refuse over guess |
| Poor capture + never-printed catalog | decisive → `assessed/elevated_risk` (not retake) | `assessed/elevated_risk` | PASS |
| Worst serialized output | no fake/genuine field or value | only `risk_band: elevated_risk` + disclaimer | PASS |
| Mixed vs clean evidence | mixed → lower confidence | 0.867 < 0.922 | PASS — honest framing |

Grep of `app/` + `migrations/` for `is_fake|is_genuine|counterfeit|verdict` and `fake|genuine|authentic`
as values: **every hit is a docstring/comment explaining the absence, or the disclaimer copy** ("not a
determination that a card is genuine or counterfeit"). No enum value, boolean field, or DB column carries
a verdict. The `RiskBand` vocabulary is closed to three bands and pinned by
`CheckConstraint("risk_band IN ('strong_signals','inconclusive','elevated_risk')")` at the column.

---

## Per-lens scores

### Security & Privacy — PASS (avg 3.0)
- Authz on the user-data path (`get_current_user`, user-scoped persist/list): **3**
- No-binary-verdict / defamation guard (charter §3.5): **3** — structural at four layers, grep-clean, ADR-backed.
- Erasure propagation: **3** — `erasure.py:77-87` enumerates `AuthenticityRecord.capture_ref` into the manifest alongside scan + pre-grade stills; docstring updated; bytes never stored (`capture_ref` only).
- Quota / COGS guard: **2** — quota charged before screening cost via shared `scan:{user_id}` key (correct: can't be sidestepped by endpoint-hopping). Docked: see Finding F1 (no quota test in this slice).

### Architecture — PASS (avg 3.0)
- Mirrors the grading provider seam (ADR 0005): **3** — `AuthenticityProvider` returns only the four visual signals; factory `build_authenticity_provider` with loud `case unknown:`.
- Catalog cross-check kept **out** of the provider seam (in-house deterministic lookup, analogue of in-house centering): **3** — `app/authenticity/catalog_existence.py` + `reference_catalog.py`, owned by the service.
- ADRs 0005 (carried) + 0006 present and sound: **3** — 0006 is precise on the type-level guard and buy→build path.
- Migration applies, no drift, batch mode for Postgres target: **3**.

### Backend — PASS (avg 2.75)
- Idiomatic async FastAPI, typed, SQL confined to repos: **3** — repo uses `select(...).where(user_id==).order_by(created_at.desc())`; no SQL in service/API.
- Error handling not happy-path: **3** — typed 404s (`card_not_found`, `capture_not_found`), 200-typed `retake`/`not_assessed`, quota 429 envelope, blank `capture_ref` rejected.
- Tests — unit + contract, adversarial: **3** — service tests assert no-verdict, catalog floor, unverifiable non-penalty, decisive-catalog-carries-poor-capture, threshold, at-threshold boundary; API tests assert the structural no-verdict field check.
- Observability / completeness: **2** — quota path on this endpoint is unexercised by the slice's own tests (F1).

### ML — PASS (avg 2.75)
- Composition honesty (confidence-weighted lean, unreadable/inconclusive contribute no direction): **3**.
- Refuse over guess (`_MIN_READABLE_SIGNALS`, `_USABLE_CONFIDENCE`, decisive-catalog override): **3**.
- Catalog tri-state with `unverifiable` widening (not penalizing) uncertainty: **3**.
- Confidence semantics: **2** — `confidence` is the *mean read-confidence of contributing signals*, not band/verdict-certainty. A confidently-read deviation legitimately keeps confidence high (0.922 on an elevated_risk floor). Defensible and honest at the per-signal layer, but see Finding F2 — the headline number could read as "we're 92% sure it's risky" to a naïve UI. Framing is the UI's job (next slice); flagging for that consumer.

### Product / PMF (honest-framing) — PASS (avg 3.0)
- Maps to a real ICP need (high-value verified collection, anti-fake as decision support): **3**.
- Honest framing — ranges/bands + confidence, never absolutes; value-gating scopes to "worth faking": **3**.
- Freemium/quota boundary respected (shared budget): **3**.
- No scope creep — mock provider, fixed reference set, no premature DB-sync: **3**.

---

## §3.6 Premium gate — PASS (zero AI-tells)

- House style matches P2.1 pre-grade (refuse posture, typed terminal states, seam shape, docstring voice). No drift.
- Naming is domain-precise (`RiskBand`, `SignalObservation`, `not_in_catalog`, `_worth_screening`) — no `handleData`/`temp`/`foo`.
- Comments explain *why* (the §3.5 rationale, the asymmetry toward inconclusive, the catalog weighting), not *what*. Dense but load-bearing — the defamation reasoning genuinely belongs in-code here.
- No dead code. `image_count` on `AuthenticityCapture` is an unused-by-mock but **forward-looking Protocol field** (holo needs multiple angles), consistent with `CaptureBundle`/`GradingCapture` — interface, not dead code. Endpoint hardcodes `image_count=1`; acceptable for the single-still mock path.
- `case unknown:` factory guard, frozen Pydantic models, check constraints — the unglamorous polish is present.

A top-tier studio would ship this. Honest yes.

---

## Findings (prioritized)

- **F1 (minor, Backend/Security):** The `/authenticity` endpoint enforces quota
  (`apps/api/app/api/authenticity.py:83-96`) but `tests/test_authenticity_api.py` has **no quota/429
  test** — the COGS guard on this endpoint is untested by its own slice (scan's tests cover the shared
  limiter, but not this route). Add a 429-path test. Does not gate.
- **F2 (minor, ML/Product — note for the UI consumer):** `AuthenticityAssessment.confidence` is mean
  read-confidence, not verdict-certainty (`services/authenticity.py:232`). A never-printed card returns
  `elevated_risk` at conf 0.922; a UI rendering "92% confident" against the risk band would mislead. The
  type/copy is honest at this layer; the **frontend slice must not present this number as
  verdict-certainty**. Flag for P3.x UI.
- **F3 (nit, Architecture):** `_AuthenticityCaptureRef.image_count` is hardcoded `1` at the endpoint
  (`api/authenticity.py:118`) while the Protocol field exists for multi-angle reads. Harmless for the
  mock; revisit when the real provider lands and capture carries true angle count.

None of F1–F3 block the gate.

---
## Gate resolution (orchestrator, 2026-06-18)
PASS all lenses + Premium gate. §3.5 defamation/no-verdict gate held structurally (4 layers: schema enum, ORM enum, DB CHECK, ADR 0006) and survived adversarial attempts to construct an accusatory/binary output. Catalog-cross-check dispositive logic, value-threshold, refuse path, and confidence-widening all independently verified; 130 tests, no migration drift; erasure manifest gap (pre-grade + authenticity capture stills) fixed. F1 (no per-slice 429 test) + F3 (hardcoded image_count) filed to #11. **F2 carried into the P3.2 brief: `confidence` is mean read-confidence, NOT verdict-certainty — the UI must never render it as "X% sure it's risky."** **GATE: PASS — merged.**
