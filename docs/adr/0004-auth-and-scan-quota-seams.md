# ADR 0004 — Auth and scan-quota seams: real user scoping now, swappable backends later

- **Status:** Accepted (build-approved). Carried findings S2 (auth) and S1 (rate-limit).
- **Date:** 2026-06-18
- **Deciders:** Backend lead (P1.4)
- **Relates to:** `docs/TECHNICAL_ARCHITECTURE.md` §1.1 (gateway: auth + rate-limit/quota),
  §5.3 (quota as the COGS control), §6 (per-user authz, GDPR); charter §3.5; master plan §4
  (the 8 scans/day free tier). Builds on the persistence layer's `User.auth_provider` /
  `auth_subject` seam.

## Context

The P1.2 persistence layer already scopes every personal row to a `User` and left the auth
linkage as nullable columns (`auth_provider`, `auth_subject`) for "a later, additive slice."
P1.4 turns the mock `/scan` into a persisted, user-scoped vertical slice and adds the
collection/portfolio endpoints. Two cross-cutting concerns must land with it, and both must
be **real now** without committing to an external vendor the project hasn't provisioned:

1. **Authentication (S2).** Endpoints must genuinely scope to a user. The architecture names
   Clerk/Supabase as the eventual IdP, but those need accounts/keys (an escalation, charter
   §5) and would block the slice. We must not ship a fake "always-admin" stand-in — that
   would make the authz and the per-user tests meaningless.
2. **Scan rate-limit / quota (S1).** §5.3 names quota as *the* COGS control: each cloud scan
   costs real money, so the free tier is capped (master plan §4: 8 scans/day). Production
   wants Redis-backed counters shared across gateway instances, which again isn't provisioned
   yet.

## Decision

Put both behind a narrow Protocol with a working in-process implementation, mirroring the
provider seam (ADR 0001) the codebase already uses.

- **`AuthProvider`** turns a bearer credential into an `AuthenticatedUser(provider, subject)`
  — exactly the pair `User` is uniquely keyed on. It does **not** touch the database;
  resolving/provisioning the `User` is the API dependency's job, so the same provider works
  for a dev token, Clerk, or a future in-house issuer. The dev backend (`DevTokenAuthProvider`)
  verifies an **HMAC-signed** `<subject>.<signature>` token: distinct subjects scope to
  distinct users, and a forged/tampered token fails a constant-time signature check. This is
  real per-user scoping — not "always admin" — with no IdP. Swapping in Clerk is a factory
  change behind `HOLOFY_AUTH_PROVIDER`, no endpoint edits.
- **`RateLimiter`** exposes one atomic `check_and_consume(key, limit) -> QuotaWindow`. Atomic
  in the interface (not check-then-increment) is what lets a Redis backend be a correct
  drop-in without a race across instances. The in-memory backend counts per `(key, UTC day)`;
  over budget returns `429 quota_exceeded` carrying the limit and seconds-to-reset. The scan
  endpoint charges quota **before** spending a recognition credit, so abuse can't drive COGS.

The user is **provisioned on first sight** of a valid token (find-or-create on the auth pair),
so dev/test needs no separate signup call; the same flow works when a real IdP's verified
subject arrives.

## Consequences

- Every user-data path is authz'd today, and the slice's tests assert real scoping
  (401 without a token, isolation between two subjects) rather than theatre.
- The COGS guard is enforced and tested (429 past 8/day, per-user) before any spend exists.
- **The dev token is dev-only.** `HOLOFY_AUTH_DEV_SECRET` must be a real secret (or the
  backend swapped to the IdP) outside `local`; it must never sign tokens against real user
  data. The in-memory limiter is single-process — correct for one instance, not a fleet;
  the Redis backend is a prerequisite for horizontal scaling.
- Tiers beyond the free quota (Premium = unlimited, credit packs) are not modelled yet —
  the limiter takes the limit as a parameter, so plan-aware quota is an additive change when
  billing (RevenueCat) lands.
- Escalation unchanged: real Clerk/Supabase + RevenueCat remain account/spend gates (charter
  §5); this slice is everything buildable without them.
