# Audit — P1.4 backend (auth, rate-limit, scan persistence, collection/portfolio)

- **Auditor:** independent backend/architecture/security auditor (adversarial; did not build this)
- **Date:** 2026-06-18
- **Artifact:** `apps/api/` — `app/auth/`, `app/ratelimit/`, `app/services/{collection,portfolio}.py`,
  `app/schemas/{collection,portfolio}.py`, `app/api/{collection,portfolio}.py`, edits to
  `app/api/scan.py`, `app/services/scan.py`, `app/api/dependencies.py`, `app/main.py`;
  tests `tests/test_{scan_flow,collection_portfolio,auth_ratelimit}.py`; ADR 0004.
- **Tests:** `60 passed in 0.84s` (reproduced). Plus an independent adversarial probe through the API.

## Verification performed (tried to falsify, not confirm)

| Claim | Result | Evidence |
|---|---|---|
| No token → 401 | PASS | probe `no-token 401`; `dependencies.py:88-89` raises `NotAuthenticatedError` |
| Tampered token → 401 | PASS | probe `tampered 401` (`invalid_credential`); `dev_token.py:41` |
| Foreign-secret (forged) token → 401 | PASS | probe `foreign 401`; HMAC verify under app secret only |
| Valid token → 200 | PASS | probe `valid 200` |
| HMAC compare is constant-time | PASS | `dev_token.py:41` `hmac.compare_digest` |
| Two tokens → two isolated users (cross-tenant) | PASS | `test_collection_portfolio.py:91` intruder sees `[]`/`0.00`; quota key is `user.id` |
| 429 past free-tier 8/day | PASS | `test_scan_flow.py:79` 9th → 429, envelope `quota_exceeded`, `limit=8`, `reset_seconds>0` |
| Rate-limit per-user | PASS | `test_scan_flow.py:101`; key `scan:{user.id}` (`scan.py:31,45`) |
| Refused scan consumes no credit / writes no record | PASS | quota charged before recognition (`scan.py:43-55`); denied path never reaches `service.scan`; `test_scan_flow.py:98` asserts only 8 records; limiter does not increment on deny (`memory.py:41-47`) |
| Consent OFF by default on persisted ScanRecord | PASS | default `False` at schema (`schemas/scan.py:35`), service sig (`services/scan.py:53`), repo (`repositories/scan.py:28`), column (`models/scan.py:86`) + CHECK constraint; opt-in only when passed (`test_scan_flow.py:31,48`) |
| SQL out of the API/service layer | PASS | all `select(...)` live in `repositories/*`; services compose repos + pricing seam |
| Error envelope used for 401/429 | PASS | both map to `HolofyError` → single `ErrorResponse` (`main.py:76-84`); probe confirmed envelope shape |

Auth is genuinely user-scoped, **not** "always-admin." The rate-limit is real, atomic, per-user, and COGS-safe. Consent is privacy-by-design (off by default, enforced at the column, revocable, erasure manifest in `app/db/erasure.py`).

## Scores

### Architecture lens
| Criterion | Score | Note |
|---|---|---|
| Fits documented design; ML/IdP stages swappable | 3 | `AuthProvider`/`RateLimiter` Protocols mirror the provider seam; Clerk/Redis are config swaps, no call-site edits |
| Module boundaries; no leaky coupling / premature abstraction | 3 | auth never touches DB (dependency provisions the user); services compose repos; portfolio delegates valuation to collection so the two can't disagree |
| Data-capture/consent loop honored | 3 | consent off-by-default, revocable, `erasure.py` enumerates out-of-band purge before cascade |
| Decisions traceable to ADR | 2 | ADR 0004 is excellent, but `config.py:76` cites the wrong ADR (A3 below) |
**Avg 2.75 — PASS** (all ≥2)

### Backend lens
| Criterion | Score | Note |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | kw-only args, frozen dataclasses, `match` factories, request-scoped UoW with commit/rollback |
| Real error handling/validation/observability | 3 | three exception handlers, request-id correlation, pydantic bounds (`quantity ge=1`, `acquired_price_eur ge=0`, `limit le=365`), confidence CHECK constraint |
| Tests: unit + integration, green | 3 | 60 green; unit for auth/limiter, integration asserts the slice contract incl. cross-tenant and quota-no-record |
| No secrets in code; EU residency / GDPR primitives | 2 | GDPR primitives strong; but the documented "secret required outside local" invariant is **unenforced** — prod boots on the insecure default (S1 below) |
**Avg 2.75 — PASS** (all ≥2)

### Security & Privacy lens
| Criterion | Score | Note |
|---|---|---|
| Authz on every user-data path | 3 | every collection/portfolio/scan route behind `get_current_user`; repos filter by `user_id`; cross-tenant probe clean |
| Explicit, revocable consent; erasure propagates to lake | 3 | `training_consent` default off + CHECK; `revoke_training_consent`; `plan_erasure` manifest targets lake scan-ids |
| Rate-limit/quota enforced (COGS) | 3 | charged before recognition spend; 429 tested; atomic interface for Redis drop-in |
| Anti-fake output never binary public verdict | n/a | not in this slice (scan returns identity + confidence ranges, no FAKE verdict) — no regression |
**Avg 3.0 — PASS** (all ≥2). Note S1 is the one deduction pressure; it sits in the backend "no secrets" criterion rather than authz, so this lens still passes, but S1 should be fixed before any non-local deploy.

## Premium / Not-Generic gate
Every criterion ≥2. AI-tell sweep:
- No generic naming, no dead code, no speculative abstraction (the two Protocols each have a concrete consumer and a documented second backend — justified, not speculative).
- Docstrings explain *why* (timezone choice, atomicity rationale, consent rationale), not *what*. House style consistent with P1.1/P1.2 repositories.
- **Two minor doc-drift tells** (A3, A4 below) — comments that are inaccurate, not narration-of-the-obvious. Borderline but real.

**Premium gate: PASS** (conditional). No blocking AI-tells; A3/A4 are trivial comment fixes that should be cleaned in the refine pass to keep the "zero AI-tells" bar honest.

## Findings (prioritized)

- **S1 (high / pre-deploy blocker, not a code bug):** `app/config.py:80` ships
  `auth_dev_secret = "dev-insecure-do-not-use-in-production"` and **nothing enforces** the
  "required outside `local`" invariant the comment and ADR 0004 both assert. Verified: `Settings(environment=PRODUCTION)`
  boots clean on the insecure default. Anyone could mint valid tokens for any subject in a
  misconfigured prod. Add a Pydantic `model_validator` that rejects the default secret (and/or
  the dev_token backend) when `environment != local`. Reasonably *deferred*: real Clerk/Supabase
  (escalation, charter §5). Not deferrable: the guard, since the default is in-repo.

- **A3 (low / doc-drift AI-tell):** `app/config.py:76` cites "ADR 0003" for the AuthProvider
  seam, but ADR 0003 is `on-device-detection`; the auth seam ADR is **0004** (`auth/__init__.py:6`
  cites it correctly). Stale cross-reference introduced this slice.

- **A4 (low / doc-drift AI-tell):** `app/schemas/portfolio.py:33` docstring says the history
  response is "with the most recent snapshot called out," but there is no such field. Remove the
  dangling clause.

- **N1 (nit):** `auth/factory.py:15` and `ratelimit/factory.py:14` `match` blocks have no
  `case _:` fallthrough. Exhaustive for the single current enum member (returns the provider),
  but a future member added to the enum without a `case` would return `None` silently. A
  `case _: raise` would fail loudly. Not a defect today.

## Verdict

**All three lenses PASS. Premium gate PASS (conditional on A3/A4 comment fixes).**
The auth and quota seams are genuine, tested adversarially, and architecturally clean — no
"always-admin," no theatre. The one item that must not ship as-is is **S1** (unenforced prod
secret guard); it is a config-validator fix, not a redesign. Recommend a light refine pass:
fix S1, correct the two stale comments (A3/A4); N1 optional.

---
## Refine & gate resolution (orchestrator, 2026-06-18)
S1 (high) fixed: `config.py` adds a `model_validator` that refuses to boot any non-`local` environment still using the insecure default `auth_dev_secret` (verified: local boots, production rejects the default, production accepts a real secret). A3 fixed: the auth-seam comment now cites ADR 0004. A4 fixed: the portfolio-schema docstring corrected to match the actual field. N1 (factory `case _` fallthrough) deferred to task #11. Suite green (60). **All lenses + Premium gate: PASS.**
