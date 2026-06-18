# Holofy — Live Status

**Updated:** 2026-06-18 · **Phase:** 0 — De-risk spikes · **Launch anchor:** before 2026-09-16

> Resume point for any session: read this file + `DEVELOPMENT_CHARTER.md` + the task backlog.

## Current phase: Phase 0 — De-risk spikes
Settle the two product-killers and two technical unknowns *before* committing real build effort (and money), per the charter loop (Plan→Build→Audit→Gate).

| Spike | Question | Status |
|-------|----------|--------|
| A — Legal price-data path | Is there a legal, reliable € (Cardmarket) price source via aggregators? | ✅ done (gate PASS) |
| Design foundation | Holofy design-token system + signature-screen spec, audited to Premium bar | ✅ done (gate PASS) |
| B — Variant disambiguation | Can set-symbol + bottom-number OCR reliably catch ×10 variant errors? | pending |
| C — On-device detection FPS | Real-time card detection on mid-range Android? | pending |
| D — Pre-grade centering | Pixel-level centering accuracy vs known graded cards? | pending |

## Done
- Master plan, technical architecture, design system synthesized (`docs/`).
- Development charter + autonomous build–audit loop defined.
- Repo + structure + backlog initialized.
- **Spike A (price-data):** technical € path PROVEN via TCGdex (live fetch, Charizard €757.10); decision = Scrydex primary + TCGdex fallback (ADR 0001). Commercial-display legal clearance still pending (see BLOCKERS).
- **Design Foundation:** bespoke "Foil Vault" token system (144 tokens, TS+CSS) + 3 signature-screen demos. Premium gate PASS (no veto).

## In flight
- Phase 0 spikes B (variant disambiguation), C (on-device FPS), D (pre-grade centering).

## Last audit results
- Spike A: Backend FAIL→PASS after adding tests (9 green); Architecture/PMF/Premium PASS. `docs/audits/spike-a-price-data.md`.
- Design Foundation: Design PASS (2.75 avg), Premium gate PASS (no veto). `docs/audits/design-foundation.md`. Polish follow-ups filed for the RN build (P1/P2/P3).

## Next
- Run Spikes B, C, D through the build→audit loop. Then Phase 0 retro → Phase 1 (core scan loop).
