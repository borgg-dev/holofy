# Audit — P1.2 Persistence Layer

**Slice:** P1.2 — Domain model + Postgres schema (card/collection/portfolio/scan + consent flag), Alembic migration, right-to-erasure, repositories.
**Auditor lens(es):** Architecture (§3.2), Backend (§3.3), Security & Privacy (§3.5), Premium / Not-Generic gate (§3.6).
**Date:** 2026-06-18 · **Auditor:** independent (did not build this slice).
**Artifact root:** `apps/api/app/db/` + `apps/api/migrations/` + `apps/api/tests/test_persistence.py`.

## Method (verified, not asserted)

- Read every file in the slice (models, repositories, `types.py`, `base.py`, `session.py`, `erasure.py`, migration, conftest, tests).
- **Ran the suite:** `PYTHONPATH=.deps:. .deps/bin/pytest -q` → **41 passed in 0.29s.** Builder's count confirmed.
- **Ran Alembic:** `upgrade head` (OK), `downgrade base` (OK), `alembic check` → **"No new upgrade operations detected"** (no drift). Verified the check is *real* by injecting a phantom column — it correctly failed with `New upgrade operations detected`.
- **Rendered the migration for Postgres** (`alembic upgrade head --sql` with a `postgresql+asyncpg` URL): emits native `UUID`, named constraints, CHECKs, and FK `ON DELETE` actions. The portability seam is genuine, not a SQLite-only hack.
- **Adversarial falsification script** against the privacy claims (consent default, revocation, FK enforcement, erasure cascade/spare, consent re-activation). Results inline below.

---

## Lens: Architecture (§3.2)

| Criterion | Score | Evidence |
|---|---|---|
| Fits documented system design; ML stages swappable | 3 | Schema maps 1:1 to TECHNICAL_ARCHITECTURE §1.1/§4: `User`/`CollectionItem`/`PortfolioSnapshot`/`ScanRecord` (personal) vs `Card`/`PriceObservation` (catalog/market). `PriceObservation` realises the "persist daily snapshots → our own price history" moat. Enums stored as portable strings, deliberately decoupled from API DTOs (`enums.py:1-9`) so persistence doesn't depend on the edge contract. |
| Clear module boundaries, no leaky coupling, no premature abstraction | 3 | Repositories are the only layer issuing SQL (`repositories/__init__.py:1-7`); services/API never touch the session query API. `types.py`/`base.py` isolate the portability seam. No speculative abstraction — `RecognitionBackend` etc. carry only shipped values. |
| Data-capture/consent loop honored (the moat) | 3 | `ScanRecord.training_consent` default `False`, `consent_revoked_at`, `consent_note`, and `list_training_eligible()` as the single read path for the data lake (`scan.py` model + repo). Consent is first-class in the schema, not bolted on. |
| Decisions traceable to ADR when non-obvious | 2 | Provider seam → ADR 0001; the persistence design choices (string enums vs native, GUID seam, erasure strategy) are documented richly in module docstrings but **no dedicated ADR** for the portability seam / erasure-manifest pattern. Docstrings carry the rationale, so traceable, but not in `docs/adr/`. |

**Lens avg: 2.75 — PASS** (all criteria ≥2).

---

## Lens: Backend (§3.3)

| Criterion | Score | Evidence |
|---|---|---|
| Idiomatic FastAPI/Python; typed; async where it matters | 3 | Fully typed `Mapped[...]` ORM, async repositories over `AsyncSession`, `async_sessionmaker(expire_on_commit=False)`, `StaticPool` only for in-memory SQLite (`session.py:25-37`). Modern SQLAlchemy 2.0 declarative style throughout. |
| Real error handling, validation, observability | 2 | Validation is pushed into the DB where it belongs: CHECK constraints (`quantity>0`, non-negative money, confidence ∈ [0,1], the consent XOR guard) and UNIQUE/FK constraints. `session_scope` is a correct commit/rollback unit-of-work. Gap: repositories surface raw `IntegrityError` to callers with no domain-error translation (P1.1 has a `HolofyError` hierarchy this layer doesn't map onto yet) — acceptable for a persistence slice, noted as a P1.4 seam. |
| Tests: unit for logic, integration for contract; green | 3 | 41 green. The cases are **meaningful, not trivial** — they assert behaviour (round-trip, idempotent upsert, distinct-reprint, consent default off + empty eligible set, revoke→ineligible, idempotent revoke, CHECK rejection via `IntegrityError`, price history ordering, dup-snapshot rejection, negative-price rejection, erasure cascade + catalog spared). I tried to falsify each privacy claim (below) and could not. |
| No secrets in code; EU residency & GDPR primitives | 3 | Migration URL read from `HOLOFY_DATABASE_URL` (`migrations/env.py:32`), no committed secret; `data_region` pinned EU; erasure + consent primitives present. |

**Lens avg: 2.75 — PASS** (all criteria ≥2).

---

## Lens: Security & Privacy (§3.5)

| Criterion | Score | Evidence |
|---|---|---|
| Authz on every user-data path; signed expiring URLs for images | 2 | **In scope-deferral, not a gap:** STATUS.md explicitly defers authz/rate-limit to P1.4 (first slice that wires user data through the request path). P1.2 is the persistence layer; repositories are user-scoped by `user_id` on every query (`list_for_user`, `history`), so the authz hook point is clean. `capture_ref` stores object-storage keys not bytes (data minimization, `scan.py:69-70`) — the signed-URL concern lives at the storage layer, a later slice. Scored 2 (the path is correctly shaped for authz, but no authz exists yet, by plan). |
| Explicit, revocable consent for training; erasure propagates to the data lake | 3 | **Falsified hard, held up.** (1) Default off: fresh scan `training_consent=False`, `list_training_eligible()==[]`. (2) Revocation works: `revoke` clears the flag, stamps `consent_revoked_at`, scan drops out of eligible set; idempotent. (3) Re-activation blocked: setting `training_consent=True` while a revocation stamp is present is rejected by `ck_scan_records_consent_not_active_when_revoked` (verified at DB level). (4) Erasure: `plan_erasure` enumerates `capture_refs` + consented `scan_ids` **before** the cascade, in-transaction — a sound, documented data-lake propagation plan (`erasure.py:1-26, 53-70`). The migration DDL carries the CHECK verbatim. |
| Rate-limit/quota enforced | 2 | Not in this slice (deferred to P1.4 per STATUS). No COGS-bearing external call path exists in the persistence layer, so nothing to rate-limit here. Scored 2 as a planned deferral; flagged so it isn't lost. |
| Anti-fake output never a binary public verdict | 3 | N/A to persistence; no fake-verdict field exists. No violation possible here. |

**Lens avg: 2.5 — PASS** (all criteria ≥2, avg ≥2.5).

### Privacy falsification log (what I tried to break)

| Attack | Result |
|---|---|
| Re-set `training_consent=True` after revocation | **Rejected** by row CHECK (`IntegrityError`). |
| Insert `ScanRecord` with a bogus `user_id` (orphan) | **Rejected** — FK enforced (under FK pragma / on Postgres). |
| Confirm revoked scan is excluded from lake-purge eligibility yet its image is still purged | Confirmed: `training_eligible_scan_ids=[]` but `capture_refs=['s3://revoked']` — image still enumerated for erasure. Correct. |
| Delete a user who owns a `Card` via a `CollectionItem` (RESTRICT on card_id) | User delete succeeds: cascade removes the `CollectionItem` first, `Card` + `PriceObservation` spared. Correct. |

---

## Premium / Not-Generic gate (§3.6)

| AI-tell | Finding |
|---|---|
| Over-commenting (what-not-why) | **Clean.** Comments explain *why* (the ×10 variant tuple, why timestamps default in Python not server-side, why string enums over native). Domain-precise, not narration. |
| Speculative abstraction / dead code / unused params | **Clean.** `RecognitionBackend` has one value because one is shipped; `types.py` notes JSONB/partial-index would live behind it *when needed*, doesn't pre-build them. No dead code found. |
| Generic naming (`handleData`/`foo`/`temp`) | **None.** Naming is domain-precise (`disambiguation tuple`, `canonical_id`, `consent_revoked_at`, `valuation_basis`). |
| Boilerplate/marketing voice; emoji-as-decoration | **None.** README and docstrings read as a working engineer's notes. |
| Inconsistent house style across files | **Consistent.** Models/db modules carry "why" docstrings; repositories are deliberately terse (method-docstrings only) — a deliberate, uniform convention, matches P1.1. `from __future__ import annotations` everywhere. |
| Missing unglamorous polish | Polish is *present*: named constraints via naming convention, FK pragma re-enabled in tests to mirror Postgres, descending-time read paths, idempotent upsert/revoke. |

**Two genuine (minor) blemishes — neither is an AI-tell, both are correctness/precision nits:**

1. **`models/price.py:45`** — comment says "a descending-time composite index" but `Index(... "card_id", "observed_at")` (line 47) is **ascending**. The `latest`/`history` queries order `observed_at.desc()`; both engines scan an ascending index backwards, so it is *functionally* fine, but the comment over-claims the index definition. Tighten the comment or use `observed_at.desc()` in the index.
2. **`models/price.py:53` + `:47`** — `card_id` carries a standalone `index=True` **and** is the leading column of the `(card_id, observed_at)` composite. The standalone single-column index is redundant for read paths the composite already covers. Mild over-indexing (extra write cost); drop `index=True` on the FK or keep deliberately for FK-only lookups and say so.

**Premium gate verdict: PASS.** Zero AI-tells; every criterion ≥2. The two nits are polish-level and do not rise to a gate failure.

---

## Verdict

| Lens | Avg | Result |
|---|---|---|
| Architecture (§3.2) | 2.75 | **PASS** |
| Backend (§3.3) | 2.75 | **PASS** |
| Security & Privacy (§3.5) | 2.5 | **PASS** |
| Premium gate (§3.6) | — | **PASS** (zero AI-tells) |

**Overall: PASS on all applicable lenses.** This is a genuinely solid, premium-bar persistence slice. Tests are meaningful and the privacy claims survive adversarial falsification at the DB-constraint level. Alembic applies up and down on SQLite and renders correctly for Postgres with no drift.

## Prioritized findings (for the refine queue — none block the gate)

1. **[Med] App-engine SQLite does not enforce FKs/cascade; only the test engine does.** `tests/conftest.py:30-34` enables `PRAGMA foreign_keys=ON` via an event listener, but `app/db/session.py:create_engine` does **not**. Verified: a migration-built `holofy.db` reports `PRAGMA foreign_keys = 0`. On the default `local` config (`database_url = sqlite+aiosqlite:///./holofy.db`, `config.py:57`) the running app silently does **not** enforce FKs or `ON DELETE CASCADE`. Production Postgres enforces natively, so this is not a prod bug — but the cascade-erasure guarantee the tests prove is **inactive in the local/dev app**, and the green suite masks it. Fix: register the same FK-pragma listener in `create_engine` for SQLite URLs (one block), so dev parity matches the tests and Postgres.
2. **[Low] `models/price.py:45` comment** claims a descending index that is defined ascending. Correct the comment or the `Index` (cite above).
3. **[Low] `models/price.py:53` redundant single-column index** on `card_id` overlapping the composite's leading column. Drop or justify.
4. **[Low] No domain-error mapping in repositories.** Raw `IntegrityError` escapes to callers; P1.1 has a `HolofyError` envelope this layer doesn't translate onto. Fine for P1.2; wire the mapping when the scan/collection write path lands in P1.4.
5. **[Low] No ADR for the persistence portability seam / erasure-manifest pattern.** Rationale is captured in module docstrings (so traceable), but a one-paragraph ADR would match the "non-obvious decision → ADR" bar of §3.2 for the GUID/string-enum/erasure choices.

---

## Refine & gate resolution (orchestrator, 2026-06-18)
Med finding #1 fixed: `app/db/session.py:create_engine` now registers a `connect` listener enabling `PRAGMA foreign_keys=ON` for SQLite, so the running app enforces FKs/cascades like Postgres (closes the dev-parity gap; no schema change, no migration impact). Low #2 fixed: the price index comment no longer over-claims a "descending" index. Low #3 (redundant single-column `card_id` index — needs a migration edit) and #4 (domain-error mapping for IntegrityError + portability ADR) deferred to task #11. Suite green (41 passed). **All lenses + Premium gate: PASS.**
