# ADR 0006 — Authenticity seam and the risk-band output contract (no binary verdict)

- **Status:** Accepted (build-approved). P3.1 — anti-fake / authenticity risk-score service.
- **Date:** 2026-06-18
- **Deciders:** Backend lead (P3.1)
- **Relates to:** `docs/TECHNICAL_ARCHITECTURE.md` §3.3 (counterfeit detection: multi-signal,
  scoped to vintage/high-value, "risk flag not a verdict"), §6 (avoid defamation risk);
  charter §3.1 (honest framing), §3.5 (the defamation rule — never a binary public "FAKE"),
  §3.6 (premium/not-generic). Mirrors the grading/capture-store seam (ADR 0005) and the
  provider seam (ADR 0001).

## Context

Counterfeit detection is **build, not buy** (§3.3) — no commodity API does it well — and it is
the riskiest output in the product to get wrong, for two different reasons:

1. **Legal/reputational.** A binary "FAKE" verdict on a specific card is a defamation hazard
   (§3.5, §6) and an over-promise the modest launch accuracy can't back. The output must be a
   *private risk flag for the owner*, never an accusation or a public claim about a card or a
   seller.
2. **Honest probabilistic framing.** Like pre-grade, the signals are noisy; a poor capture or
   a cheap card must not get a fake-precise score (§3.1).

The signals themselves are heterogeneous: four *visual* cues (print-pattern/rosette, holo
signature, font/layout, cardstock) that a future CV ensemble reads, plus one *deterministic*
cross-check — does the resolved `(set, collector number, variant, era)` tuple correspond to a
printing that **actually exists**? A card that was never printed in that form is the strongest
single fake contributor, and artwork matching alone can't catch it.

## Decision

Mirror the grading seam (ADR 0005): a provider for the learned/rented signals, with the
deterministic, auditable signal kept *out* of it — and encode the §3.5 guardrail in the
**types**, not in copy.

- **`AuthenticityProvider`** (`app/providers/base.py`) returns **only the four visual signals**,
  each an `AuthenticitySignal` (observation band + the provider's own confidence). The CV
  ensemble drops in behind this exact signature later; the service never knows whether a read
  was bought, built, or mocked. Factory `build_authenticity_provider` selects by
  `HOLOFY_AUTHENTICITY_PROVIDER` with a loud `case _:`.
- **The catalog-existence cross-check is *not* behind the provider seam.** It is a deterministic
  reference-DB lookup (`app/authenticity/catalog_existence.py` + `reference_catalog.py`) the
  service owns — the analogue of keeping in-house centering out of `GradingProvider`. Its result
  is tri-state: `confirmed` / `not_in_catalog` / **`unverifiable`**. An absent reference is *our*
  gap, so `unverifiable` widens uncertainty and **never** counts against the card.
- **Output is a `RiskBand`, never a boolean.** The only three values are `strong_signals` /
  `inconclusive` / `elevated_risk`. There is no `is_fake` / `is_genuine` / `verdict` field
  anywhere — in the DTO, the ORM model, or the persisted row (a check constraint pins
  `risk_band` to the three-band vocabulary). The most adverse thing the service can emit is
  "elevated risk — seek professional authentication". A `not_in_catalog` read is *dispositive*:
  a never-printed variant floors the band at `elevated_risk` regardless of clean visuals.
- **Value-threshold gating.** Screening is only meaningful on cards worth faking (§3.3:
  "scoped to vintage/high-value"). Below `HOLOFY_AUTHENTICITY_MIN_VALUE_EUR` the service returns
  a typed `not_assessed` ("not needed for this value") rather than a fake-precise score; an
  unpriced card is treated as below-threshold.
- **Refuse over guess.** Below a usable-evidence floor (too few signals read confidently, and
  no decisive catalog read) the service returns `retake` with capture coaching — never a
  confident wrong band. Unreadable signals widen uncertainty; they are never scored as evidence.

## Consequences

- The §3.5 defamation rule is structural and grep-able: no code path, field, enum value, or DB
  column can carry a binary fake/genuine verdict. The disclaimer is allowed to *explain* the
  guardrail ("not a determination that a card is genuine or counterfeit"); nothing asserts one.
- The buy→build path holds: the CV ensemble is a single factory line later, and the catalog
  cross-check — the most defensible signal — stays in-house and auditable.
- Mock provider + reference catalog + synthetic capture store mean the whole slice runs with no
  models, no catalog sync, and no network; the never-printed-variant case is testable today.
- `AuthenticityBackend` has only `mock`; the reference catalog is a small fixed set until the
  nightly reference-DB sync (architecture §4) owns it — at which point the
  `CatalogExistenceChecker` Protocol takes a DB-backed implementation with no service change.
- The screen shares the free-tier daily budget with scan and pre-grade (one quota key), so the
  COGS guard can't be sidestepped by hopping endpoints.
