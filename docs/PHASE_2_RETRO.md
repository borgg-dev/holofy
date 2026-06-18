# Phase 2 Retro — Pre-grade v1 (mock-first)

**Date:** 2026-06-18 · **Outcome:** GREEN — pre-grade runs end-to-end on mocks, honest-framing enforced structurally; no plan-level fork.

## What shipped
The pre-grade differentiator: scan/reveal → **Pre-grade** → guided multi-angle capture → a **grade probability range + per-axis sub-scores + confidence** (or a retake refusal). The Spike-D centering algorithm is now real, in-house production code.

| Unit | Delivered | Tests |
|------|-----------|-------|
| P2.1 | Pre-grade backend: in-house centering + GradingProvider seam (mocked corners/edges/surface) → range + P(≥X) + confidence; `POST /pregrade`; persisted; refuse-on-bad-capture | 99 backend |
| P2.2 | Mobile: guided multi-angle capture (skew + glare coaching) + bespoke SVG range-band gauge + retake state | 64 mobile |
| P2.cleanup | Whole mobile codebase compiles clean under `tsc --strict` (7→0) | 64 mobile |

## Honest-framing held under adversarial audit
The hard trust/legal requirement — *never present an absolute grade* — is enforced **structurally, not cosmetically**:
- No `grade` field exists anywhere in the schema, model, or mobile types (regression-tested both sides).
- Output is a **range + P(≥X) + confidence + disclaimer**; a DB CHECK forbids an inverted band.
- **Worst-axis gating**: a card with one bad axis can't read high (verified: corners/edges 10, surface 1 → 3–4 range).
- Low confidence **widens** the band and lowers confidence; below the centering floor it **refuses** with a retake signal rather than guessing.
- The auditor ran a full 5⁴×5 score/confidence sweep — zero incoherent payloads, no false-precision input constructible.
- Mobile: low confidence is **amber, never red**; disclaimer + PSA/CGC/Nintendo non-affiliation are persistent and non-dismissible.

## The loop kept earning its keep
- P2.1 fixed the carried factory `case _` polish in flight.
- P2.2 audit **confirmed 7 pre-existing `tsc --strict` errors** that had quietly accumulated across P1.4 screens — caught, tracked, and cleared (principled typing, no `any`/`@ts-ignore`) before closing the phase. The strict codebase now compiles clean.

## Carried debt (non-blocking, tracked in #6/#11)
- ADR 0005 for the GradingProvider/CaptureStore seam; thread a real `image_count`; CORS tightening; redundant-index removal + IntegrityError mapping; remaining real-camera states (permission-denied/empty) — these land with the `expo-camera` integration, not before (faking them would violate the honesty bar).

## Decision: proceed to Phase 3 — Anti-fake v1 + data loop
Build the counterfeit/authenticity feature (the second differentiator) and wire the consented data loop (the moat):
- **Anti-fake**, mock-first: a multi-signal authenticity **risk score** scoped to vintage/high-value, output as "no counterfeit indicators / seek expert review" — **never a binary 'FAKE'** (defamation + reputational safety, charter §3.5). Behind a provider seam like grading.
- **Data loop**: the explicit, revocable training-consent UX + the scan→data-lake capture seam (consent model already exists from P1.2; this makes it real end-to-end).
Still mock-first; no blocker on the critical path.
