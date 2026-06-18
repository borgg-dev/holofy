# Phase 4 Retro — Stack Scanning + Dev-Mode Ready

**Date:** 2026-06-18 · **Outcome:** GREEN — high-volume stack scanning runs end-to-end; and the whole product is now proven to **run in dev mode**, live, mock-first.

## What shipped
| Unit | Delivered | Tests |
|------|-----------|-------|
| Dev-mode proof | `scripts/dev_smoke.sh` + `smoke_journey.py` boot a fresh API and drive the full journey over HTTP; top-level `Makefile`; `docs/DEV_RUNBOOK.md` | live |
| P4.1 | `POST /scan/batch`: shared `classify()` path, identity dedupe, COGS-safe charge-before-recognize quota | 170 backend |
| P4.2 | Mobile rapid scan: filmstrip + dedupe-merge + confirm-at-end review + bulk add; explicit ID+value-only boundary | 135 mobile |

## The headline: "dev-mode ready" is now real, not asserted
Previously every "done" rested on unit tests. This phase added the missing proof: `make api-smoke`
boots the server and walks the real product over HTTP — scan (both outcomes incl. the live €732.60
confirm delta), stack scan, collection, portfolio, pre-grade range, authenticity risk-band (no verdict),
account-level consent — **mock-first, no keys**. That is the genuine dev-mode bar.

## The loop caught a serious one
P4.1 **failed its audit on COGS safety**: the batch recognized every capture *before* the quota gate, so
an exhausted-budget user could still trigger 50 recognition calls (real money). Refined to charge-before-
recognize per capture (a budget-exhausted capture never reaches the recognizer), proven by a counting-spy
test that runs the auditor's exact 50-item falsification and asserts **zero** recognitions. This is exactly
the kind of cost-safety bug that only a real adversarial audit catches — and it would have hurt in production.

## Where the build stands — the autonomous mock-first roadmap is essentially COMPLETE
Everything that can be built without the founder's external resources now exists and runs:
- Full market-fit MVP (scan / € value / portfolio / pre-grade / anti-fake / consented data loop) + stack scanning.
- Backend boots and serves the whole journey live; mobile compiles clean under strict TS, every screen renders.
- 19 commits, ~300 files, 18 independent audit reports, hard gates (defamation, privacy, honest-framing, COGS) all held.

## Decision: Phase 5 — productionization (autonomous) + the mocks→real boundary (founder)
- **Autonomous, no keys needed (P5.1):** Docker + docker-compose (api + Postgres + Redis), run against real
  Postgres, a real Redis rate-limiter behind the seam, CI, env templates — verifiable productionization.
- **Coded-not-activated (P5.2):** real provider adapters (Ximilar recognition, commercial pricing, OAuth,
  billing) behind the existing seams, contract-tested against mocked HTTP; activated by config when keys arrive.
- **Genuinely needs the founder (BLOCKERS.md):** the keys/accounts/legal that flip mocks→real and a couple of
  provider decisions (which OAuth, which billing). These are the real unlocks from dev-mode → production.
