# Phase 1 Retro — Core Scan Loop (mock-first)

**Date:** 2026-06-18 · **Outcome:** GREEN — the core scan loop runs end-to-end on mocks; no plan-level fork.

## What shipped
The first demoable product: **scan → identify → € value → add to Vault → portfolio**, plus the low-confidence **confirm** path — entirely on mocked external services, behind swappable seams.

| Unit | Delivered | Tests |
|------|-----------|-------|
| P1.1 | FastAPI backend; swappable Recognition/Pricing providers; consolidated TCGdex pricing; `/scan` | 27 |
| P1.2 | Async SQLAlchemy persistence; Alembic migrations; consent/erasure (privacy-by-design) | +14 |
| P1.3 | Expo/RN app on compiled design tokens; bespoke scan-frame screen | tsc |
| P1.4 | Auth seam (user-scoped) + rate-limit + persisted scan + collection/portfolio; Reveal/Confirm/Vault screens | backend 60, mobile 26 |

## The loop earned its keep — three real catches the audits forced
1. **IP VETO (P1.4 mobile):** mock/demo data was saturated with real Pokémon names/sets — a direct hit on our hard legal gate. Caught, traced to a project-wide mock decision, and remediated to invented neutral cards *while preserving* the 30.9× variant price-split the Confirm screen needs.
2. **Insecure auth default (P1.4 backend, high):** the dev signing secret could ship unguarded; now a validator refuses to boot a deployed env on the default.
3. **Dev-parity FK gap (P1.2):** SQLite FK enforcement was test-only; now enforced at runtime so cascades behave like Postgres.

Plus a dropped builder mid-P1.4 (mobile) — recovered by inspecting on-disk state and dispatching a completion builder, no work lost.

## Architecture proven out
- **Mock-first works.** The whole product runs with zero credentials; real providers (Ximilar, aggregator, OAuth, Redis, billing) drop in behind Protocols + factories with no call-site changes. The batched BLOCKERS stay off the critical path.
- **The confirm pattern is load-bearing** and now real end-to-end: below the confidence threshold, the user disambiguates top-2 with the € delta — never a silent ×30 misprice.
- **Consent/data-loop wired from the first feature** (the moat), defaulting safe.

## Carried debt (non-blocking, tracked)
- Task #6 (design carry-overs) and #11 (polish): factory exhaustiveness guards, redundant index removal + IntegrityError mapping, remaining scan-frame states (permission-denied, empty), a few ADRs. Apply during Phase 2.

## Decision: proceed to Phase 2 — Pre-grade v1
Build the pre-grading feature: promote the Spike-D centering algorithm into a real in-house service (the honest, defensible signal), with corners/edges/surface behind a mocked grading provider seam, surfaced as a **grade probability range + confidence** (never an absolute grade) on the Reveal/Pre-grade screen. Guided multi-angle capture is the hard capture↔ML dependency to honor. Still mock-first for the bought sub-scores; no blocker on the critical path.
