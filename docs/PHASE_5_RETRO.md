# Phase 5 Retro — Productionization + the Mock-First Finish Line

**Date:** 2026-06-18 · **Outcome:** the autonomous **mock-first product is finished**; what remains is founder-gated activation (see `BLOCKERS.md`).

## What shipped (P5.1)
- **Real Redis rate limiter** behind the existing `RateLimiter` Protocol — atomic Lua check-and-consume (correct across instances), behaviour-equal to the in-memory limiter. **Verified** with `fakeredis` (real Lua via `lupa`): allow-to-limit, denied-consumes-nothing, per-key isolation, TTL window, factory selection. Backend suite 175 green.
- **Deploy scaffold** (authored; see honesty note): `Dockerfile` (non-root, migrate+serve), `docker-compose.yml` (api + Postgres + Redis with healthchecks), `apps/api/.env.example`, and `.github/workflows/ci.yml`.

## Honesty note — what's verified vs authored
This sandbox has **no Docker, Postgres, or Redis and no root**, so the container/DB/queue stack
could not be *run* here. I did not claim it works. Instead:
- The Redis limiter logic is genuinely verified (fakeredis).
- The Docker/compose/CI are authored and YAML-validated, and **the CI is where they actually get
  exercised** — on every push it runs the suite, then migrates + runs the live smoke against **real
  Postgres + Redis service containers**, builds the native + web bundles, and uploads app
  screenshots as artifacts. That closes the verification gap I can't close locally.

## What I deliberately did NOT build (and why)
**P5.2 real provider adapters (Ximilar recognition/grading, OAuth, billing).** Writing these now
would be speculative: they can't be tested without keys, the response shapes can't be confirmed
without live access, and recognition additionally needs real capture-image storage that doesn't
exist yet. That's the exact "looks done, isn't verified" trap that the gitignored-fonts / never-built-app
failure taught us to avoid. The **seams are built and waiting**; activation is a config change once
the keys/decisions in `BLOCKERS.md` arrive. The one real external data path that needs no key —
TCGdex pricing — already exists and works.

## The lesson that reshaped this phase
Earlier "done"s rested on unit tests + subagent reports. Two real failures exposed the gap:
the mobile app had **never been built** (gitignored fonts), and a builder reported a COGS-safe
batch that **wasn't** (recognition before the quota gate). Fix: "done" for anything runnable now
means *I ran the real command and watched it pass* — `make api-smoke` (live HTTP journey),
`make mobile-build` / `make mobile-web` (real bundles), clean-clone reinstall reproduction.

## Where the product stands
- **Backend:** runs live, mock-first, 175 tests + live smoke. ✅
- **Mobile:** builds reproducibly (android + web), 135 tests, tsc 0; `make mobile-watch` runs it with fake data. ✅ (pixels not eyeballed here — no browser in the sandbox; CI renders screenshots.)
- **Productionization:** Redis limiter real; Docker/compose/CI authored, CI-verified on push.
- **Still mock:** recognition / grading / authenticity intelligence (fixtures); real auth/billing/cloud.
- **Finish line:** the mock-first build is complete. Real/launchable is gated on `BLOCKERS.md`.
