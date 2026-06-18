# Holofy — Live Status

**Updated:** 2026-06-18 · **Phase:** 1 COMPLETE → entering Phase 2 (Pre-grade v1) · **Launch anchor:** before 2026-09-16

## Phase 1 — core scan loop: COMPLETE ✅ (retro: docs/PHASE_1_RETRO.md)
| Unit | What | Status |
|------|------|--------|
| P1.1 | Backend skeleton + swappable mock providers + consolidated TCGdex pricing + /scan | ✅ done (27 tests) |
| P1.2 | Persistence: models + Alembic + consent/erasure (privacy-by-design) | ✅ done (+14 tests) |
| P1.3 | RN/Expo scaffold on compiled design tokens + scan-frame screen | ✅ done (no veto) |
| P1.4 | Vertical slice: auth + rate-limit + persisted scan + collection/portfolio; Reveal/Confirm/Vault screens | ✅ done (backend 60, mobile 26) |

The core scan loop runs end-to-end on mocks: scan → identify → € value → confirm (if low-confidence) → add to Vault → portfolio. Auth secret hardened; **all Pokémon IP removed from shipped mock data** (invented cards, 30.9× split preserved).

## Phase 2 — Pre-grade v1 (next)
| Unit | What | Status |
|------|------|--------|
| P2.1 | Pre-grade service: Spike-D centering in-house + mocked grading seam → grade probability range + confidence | next |
| P2.2 | Mobile: guided multi-angle capture + pre-grade gauge screen (range + sub-scores + disclaimer) | blocked by P2.1 |

Carried non-blocking polish: tasks #6 (design) + #11 (backend/mobile findings) — apply during Phase 2.


> Resume point for any session: read this file + `DEVELOPMENT_CHARTER.md` + the task backlog.

## Current phase: Phase 0 — De-risk spikes
Settle the two product-killers and two technical unknowns *before* committing real build effort (and money), per the charter loop (Plan→Build→Audit→Gate).

| Spike | Question | Status |
|-------|----------|--------|
| A — Legal price-data path | Is there a legal, reliable € (Cardmarket) price source via aggregators? | ✅ done (gate PASS) |
| Design foundation | Holofy design-token system + signature-screen spec, audited to Premium bar | ✅ done (gate PASS) |
| B — Variant disambiguation | Can set-symbol + bottom-number OCR reliably catch ×10 variant errors? | ✅ done (gate PASS) |
| C — On-device detection FPS | Real-time card detection on mid-range Android? | ✅ done (gate PASS) |
| D — Pre-grade centering | Pixel-level centering accuracy vs known graded cards? | ✅ done (gate PASS) |

## Done
- Master plan, technical architecture, design system synthesized (`docs/`).
- Development charter + autonomous build–audit loop defined.
- Repo + structure + backlog initialized.
- **Spike A (price-data):** technical € path PROVEN via TCGdex (live fetch, Charizard €757.10); decision = Scrydex primary + TCGdex fallback (ADR 0001). Commercial-display legal clearance still pending (see BLOCKERS).
- **Design Foundation:** bespoke "Foil Vault" token system (144 tokens, TS+CSS) + 3 signature-screen demos. Premium gate PASS (no veto).

- **Spike B (variant disambiguation):** PROVEN — 31 printings named "Charizard" span €1.95→€4,043 (×2,074); identical-art printings separable only by collector-number+set. Pipeline: recognise→OCR number+classify symbol→resolve→low-confidence shows top-2 with € delta. OCR on phone photos ~80–90% (capture-quality gated). ADR 0002.
- **Spike C (on-device FPS):** FEASIBLE — YOLO11n @320px int8, ~20–30 FPS mid-range, stack mode ~75–100 cards/min even on fallback tier. Riskiest unmeasured number: mid-range latency (~32ms, on the 30 FPS knife-edge) — settle on real hardware. ADR 0003.
- **Spike D (pre-grade centering):** WORKS — pure-numpy pixel-level centering, 0px error on 400 synthetic cards, honest confidence (measurement-quality, not centering-quality). Hard dependency: needs deskewed/flat capture (perspective is the top real-world risk). `spikes/centering/`.

## Phase 0 verdict: GREEN — no plan-level forks
All four de-risk questions resolved positively. Both product-killers cleared technically (price path proven; variant disambiguation proven). One unresolved item is **legal, not technical**: commercial-display clearance for aggregator-sourced € prices (BLOCKERS). Recurring theme across spikes: **capture quality is the universal accuracy ceiling** — the guided-capture scan-frame is a hard cross-team dependency for recognition, OCR, centering, and anti-fake alike.

## In flight
- Phase 0 retro (next) → Phase 1 kickoff (core scan loop).

## Last audit results (Phase 0 iteration 2)
- Spike B: Architecture/Backend/ML + Premium PASS (zero AI-tells). `docs/audits/spike-b-variant-disambiguation.md`.
- Spike C: Architecture/ML + Premium PASS (numbers re-derived from the helper, sourced). `docs/audits/spike-c-on-device-fps.md`.
- Spike D: lenses PASS; Premium gate conditional → 1 dead-code AI-tell fixed → PASS. `docs/audits/spike-d-centering.md`.

## Next
- Write Phase 0 retro. Then Phase 1 (core scan loop). **Phase 1 integration will hit BLOCKERS** (Ximilar key, aggregator tier, dev accounts, legal) — surface batched before real-service wiring; build against mocks meanwhile.
