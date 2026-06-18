# Phase 3 Retro — Anti-fake v1 + Data Loop (mock-first)

**Date:** 2026-06-18 · **Outcome:** GREEN — authenticity screening + the consented data loop run end-to-end on mocks; the market-fit MVP's two differentiators (pre-grade + anti-fake) are now both built; no plan-level fork.

## What shipped
| Unit | Delivered | Tests |
|------|-----------|-------|
| P3.1 | Authenticity risk-score backend: AuthenticityProvider seam (mocked signals) + in-house catalog cross-check → risk band + confidence + "seek professional authentication"; value-threshold gating; refuse path | 130 backend |
| P3.3 | The consented data loop (the moat): DataLakeSink seam + single consent-gated emit; account-level training consent (model + UX); GDPR erasure across all capture kinds | 148 backend / 73 mobile |
| P3.2 | Mobile authenticity verdict: bespoke shield (teal/amber), per-signal breakdown, separated evidence-quality, not_assessed/retake states | 106 mobile |

## The two hard gates this phase existed to protect — both held
1. **No-verdict / defamation (§3.5):** there is no `fake`/`genuine`/`counterfeit` verdict field anywhere — enforced structurally (schema enum + ORM enum + DB CHECK + ADR 0006 on the backend; closed 3-band Record + regression tests on mobile). The most adverse output the product can ever show is amber *"some signals don't match — we recommend professional authentication."* Auditors tried and failed to construct an accusatory or binary output on both sides.
2. **Privacy / consent (§3.5):** the data loop has a **single emit gate**; a non-consented or revoked record can never reach the data lake (proven by test at unit + API boundary). Consent defaults OFF, is account-level, revocable, and erasure propagates to lake examples across scan/pre-grade/authenticity.

## The loop kept catching real things
- **P3.3 consent UX failed Design/Premium** on an inverted screen-reader label, a dark-pattern button weight (with a comment that *lied* it was "equal weight"), and a consent-persistence bug (count-derived). All three refined → re-audited → cleared. These are precisely the trust-eroding details a "premium, trustworthy" product can't ship.
- Carried debt cleared in-flight: ADR 0005 (grading seam, previously undocumented) + 0006; the GDPR erasure manifest extended to pre-grade + authenticity stills (a real pre-existing gap); all provider factories given `case _:` guards.
- The P3.1 framing finding (confidence = read-confidence, not verdict-certainty) was carried forward and **honored in the P3.2 UI** — confidence is shown only as separate "evidence quality."

## Carried debt (non-blocking, tracked in #6/#11)
Most notable: **F1 (P3.2)** — the backend per-signal `detail` is free-text; before the real authenticity provider integrates, add a non-accusatory content contract (the type system blocks an accusatory *band* but not an accusatory *sentence*). Plus: image_count threading, a per-slice 429 test, consent-UI render tests, tabular evidence %, and the real-camera states that land with the `expo-camera` swap.

## Where the product stands
The full **market-fit MVP feature set now runs end-to-end on mocks**: scan → identify → € value (Cardmarket-native) → confirm low-confidence variants → portfolio → pre-grade (range + confidence) → authenticity screening (risk band, no verdict) → consented data loop. Everything sits behind swappable provider seams; the batched BLOCKERS (legal price-display clearance, Ximilar/aggregator keys, dev accounts, billing, OAuth, Redis) gate only the switch from mocks to real services — none are on the build critical path.

## Decision: proceed to Phase 4 — Stack / high-volume scanning
Per the architecture roadmap: continuous multi-card "scan a stack" capture with on-device dedupe and confirm-at-end (ID + value only; grade/authenticity stay single-card guided per the capture↔ML constraint). Then Phase 5 (proprietary models / cost-down) and the real-service integration once blockers clear. Still mock-first; no blocker on the critical path.
