# Phase 0 Retro — De-risk Spikes

**Date:** 2026-06-18 · **Outcome:** GREEN — all de-risk questions resolved, no plan-level fork.

## What we set out to settle
The two product-killers and two technical unknowns, *before* spending real build effort or money.

| Spike | Question | Result |
|-------|----------|--------|
| A | Legal, reliable €/Cardmarket price source? | **Technically YES** (live proof, no key). Legal display clearance pending. |
| B | Can collector-number + set-symbol catch ×10 variant errors? | **YES** — ×2,074 spread on one name; identical-art reprints separable only by the tuple. |
| C | Real-time on-device card detection on mid-range phones? | **YES** — YOLO11n@320 int8, ~20–30 FPS mid, stack ~75–100 cards/min. |
| D | Pixel-level centering accuracy? | **YES** — 0px error on 400 synthetics; honest confidence model. |
| Design | A bespoke, premium, non-generic identity? | **YES** — Foil Vault system; Premium gate passed with no veto. |

## The loop worked as designed
- 6 work units, each Plan→Build→Audit→Gate. Builders and auditors were always **distinct agents**.
- The audit caught real defects and **blocked commits until fixed**: Spike A (missing tests → added 9), Spike D (dead-code AI-tell → removed). This is the rigor the charter promises, demonstrated, not asserted.
- Premium gate held: zero generic/AI-tell output shipped.

## Cross-cutting findings (carry into every later phase)
1. **Capture quality is the universal accuracy ceiling.** Recognition, collector-number OCR, centering, and anti-fake all degrade on poor captures. The guided-capture scan-frame (teal-lock + quality gate + deskew) is therefore the single highest-leverage cross-team dependency — it gates ML accuracy, not just UX. Prioritize it early in Phase 1.
2. **Low-confidence → confirm, never silently guess.** The variant pipeline turns its hardest cases into a top-2 + €-delta user confirmation, which also harvests consented training labels. Generalize this pattern.
3. **The moat is the data loop.** Every confirmed scan / centering / later real-grade pair is a training example. Wire consented capture from the first real feature.
4. **One unmeasured number to settle on hardware:** mid-range detection latency (~32ms, on the 30 FPS edge). Contained risk — worst case shifts the device floor to a coached ~20 FPS tier.

## The one open item — legal, not technical
Commercial-display clearance for aggregator-sourced Cardmarket € prices (Scrydex terms or a legal opinion). Tracked in `BLOCKERS.md`. Does not block building Phase 1 against mocked pricing.

## Rubric / process adjustments for Phase 1
- Keep the distinct-builder/auditor rule; it paid off.
- Add an explicit "tests exist + are non-circular" check to the builder brief up front (both test gaps in Phase 0 were foreseeable).
- Fold the duplicated TCGdex client helpers (Spikes A/B) into one shared pricing module when Phase 1 builds the real pricing service.

## Decision: proceed to Phase 1
Build the **core scan loop** (capture → recognize → match → € value → portfolio) against **mocked external services**, so no blocker is on the critical path. Real-service integration (Ximilar, aggregator, billing) waits on the batched BLOCKERS and lands behind the same swappable interfaces the architecture already specifies.
