# Audit — P3.3 Consented Data Loop (the moat)

**Auditor lenses:** Security & Privacy (GDPR), Architecture, Backend, Design, Premium gate (§3.6, VETO on consent UX), Product/PMF (§3.1).
**Date:** 2026-06-18
**Verdict:** PASS on Security/Privacy, Architecture, Backend, Product/PMF. **Design FAILS** (a11y label inversion + dark-pattern button weight). **Premium gate FAILS** (the consent UX carries AI-tells: a comment that contradicts the code).

The privacy hard line itself holds. The failures are on the *UX* of consent, not the data path.

---

## Build / test evidence (all run, all green)

| Check | Result |
|---|---|
| `pytest -q` (api) | **141 passed** |
| `alembic upgrade head` | clean, 4 migrations apply |
| `alembic check` | **No new upgrade operations detected** (no drift) |
| `design-tokens build.mjs` | 146 tokens written |
| `mobile npm test` | **73 pass / 0 fail** |
| `tsc --noEmit` (mobile) | **0 errors** (strict compile not regressed) |

---

## PRIVACY HARD LINE — verified by falsification

**There is genuinely ONE gate.** Every emission site (scan service, pregrade endpoint, authenticity endpoint) calls `emit_scan` / `emit_pregrade` / `emit_authenticity` in `app/datalake/emit.py`. Each `emit_*` short-circuits with `return False` **before** `sink.emit()` is reached unless `_is_consented(training_consent, consent_revoked_at)` — i.e. `training_consent is True AND consent_revoked_at is None` (`emit.py:25-31`).

- `grep` for `sink.emit` / `data_lake.emit` outside `app/datalake/` returns **nothing** — no call site touches a sink directly; the gate cannot be bypassed.
- The same predicate is reused in three places (`emit.py:31`, each repo's `list_training_eligible`, and `db/erasure.py:_eligible_ids`), so the live gate, the batch-ingest gate, and the erasure target can never disagree about what "consented" means.

**Tests are real, not theatre:**
- `test_non_consented_scan_emits_zero_examples` asserts `sink.examples == []` *and* that the record was still persisted as history (`test_datalake.py:103-113`) — proves zero-emission, not just a truthy assertion.
- `test_revoked_consent_record_never_emits` records with consent, revokes, then asserts `emit_scan(...) is False` and `sink.examples == []` (`test_datalake.py:117-133`).
- Pregrade + authenticity have the matched consented=1/non-consented=0 pair (`test_datalake.py:136-226`).
- At the **API boundary**, `test_non_consented_scan_never_reaches_the_lake` and `test_consented_scan_reaches_the_lake_and_revoke_stops_future_ones` drive the real TestClient and inspect `app.state.datalake_sink` (`test_consent_api.py:61-86`).

**Consent default OFF — verified both sides:**
- Backend: model columns default `False` (`scan.py:86`, `pregrade.py:113`, `authenticity.py:109`); request schemas default `training_consent: bool = False` (`scan.py:35`, `grading.py:101`, `authenticity.py:123`); repository `record(... training_consent=False ...)`.
- Mobile: client params default `trainingConsent = false` and the body is *always* sent explicitly (`client.ts:130,137,166,172`). HTTP-body assertions prove it: `test sends training_consent=false on a scan unless explicitly opted in` parses the actual request body and asserts `false` (`consent.test.ts:110-119`); the `true` case only fires on explicit opt-in (`consent.test.ts:121-130`). The builder's claim is genuine.

**GDPR erasure — covers all three kinds:** `ErasureManifest` enumerates `capture_refs` for scan+pregrade+authenticity and `training_eligible_{scan,pregrade,authenticity}_ids` using the shared predicate, *before* the cascade drops the rows (`erasure.py:64-128`). A consented pregrade/authenticity example cannot survive a delete.

---

## Per-lens scores

### Security & Privacy (GDPR) — **PASS** (avg 2.9)
| Criterion | Score | Note |
|---|---|---|
| Single consent gate, non-consented/revoked never reaches sink | 3 | One gate, no bypass path, proven by falsification tests |
| Consent default OFF (both sides) | 3 | Columns, schemas, client defaults, body-assert tests all confirm |
| Revocation propagates / marks for purge | 3 | `revoke_*_for_user` stamps `consent_revoked_at`; constraint `NOT (training_consent AND revoked)` forbids the contradiction at the row |
| Erasure reaches the lake for all 3 kinds | 3 | `erasure.py` manifest enumerates all three before cascade |
| Data minimization (refs, never bytes) | 3 | `capture_ref` only; documented at each column |
| Authz on the consent path | 2 | User-scoped via bearer token; always caller's own state (`consent.py`). No quota on privacy mgmt is correct |

### Architecture — **PASS** (avg 2.8)
| Criterion | Score | Note |
|---|---|---|
| Sink seam mirrors provider pattern | 3 | `DataLakeSink` Protocol + `factory.build_datalake_sink` mirror `app.providers.*`; emitters depend only on the Protocol |
| Module boundaries / no leaky coupling | 3 | Gate expressed once in `emit.py`; async boundary documented for the real lake |
| Migration backfills existing rows safely | 3 | `server_default=sa.false()` backfills as not-consented, then dropped to match the Python-side default (`...ae8e7df2bb19...py`) |
| Decisions traceable | 2 | Inline rationale is thorough; no dedicated ADR for the sink seam, but it follows an established pattern |

### Backend — **PASS** (avg 3.0)
| Criterion | Score | Note |
|---|---|---|
| Idiomatic FastAPI/typed/async | 3 | Clean DI, typed throughout, async sink |
| Error handling / not happy-path | 3 | Quota-before-cost, typed 404s, retake/not-assessed bodies; emit no-ops are explicit |
| Tests: unit + integration, green | 3 | 141 pass; unit gate tests + API-boundary tests + idempotency test |
| No secrets; GDPR primitives | 3 | Config-switched sink; erasure + consent primitives present |

### Product / PMF — **PASS** (avg 2.8)
| Criterion | Score | Note |
|---|---|---|
| Maps to the moat (consented dataset) | 3 | Exactly the §2/§6 data-loop slice |
| Honest framing (no absolutes) | 3 | Disclaimers structural; risk *band* not verdict; labels carry band not boolean |
| Freemium/quota respected | 3 | Shared `scan:{user_id}` key across the three COGS endpoints can't be sidestepped |
| No scope creep | 2 | Stays in lane; the per-record-vs-account-level consent model (below) is a slight conceptual stretch but defensible |

### Design — **FAIL** (criterion below 2)
| Criterion | Score | Note |
|---|---|---|
| Bespoke, token-driven | 3 | `ConsentToggle` is a custom switch (not platform `<Switch>`), token-driven, lights the "lock" hue |
| Real states (loading/error/save-error) | 3 | Skeleton load, retry on load error, rollback + inline message on save error |
| Intentional motion + reduced-motion | 3 | Knob eases; `useReduceMotion` snaps it (`ConsentToggle.tsx:28-38`) |
| Accessibility (role=switch, 44pt, labels) | **1** | role=switch + checked state + 44pt present, **but the spoken label is inverted** (finding D1) |

### Premium / §3.6 gate (consent UX) — **FAIL** (one AI-tell)
The consent UX is genuinely high-craft (bespoke toggle, restraint, honest copy, real states). It fails the gate on the **comment-contradicts-code** AI-tell (finding D2): `FirstCapturePrompt.tsx:18-19` asserts "Not now" has "the same prominence" / "equal weight," while the code gives accept `tier="primary"` (accent fill, 52pt, title text) and decline `tier="tertiary"` (text-only, secondary tone). §3.6 auto-fails on comments that don't match reality and on the un-spotted polish miss. Both findings are small and fixable.

---

## Prioritized findings

**P1 — D1 (a11y): inverted screen-reader label on the consent toggle.**
`PrivacyScreen.tsx:169` passes `consent.granted ? copy.toggleA11yOff : copy.toggleA11yOn`. The copy strings describe the *current* state — `toggleA11yOn` = "Sharing… is **on**…", `toggleA11yOff` = "Sharing… is **off**…" (`copy.ts:26-27`). So when sharing is ON, the reader is handed "Sharing… is **off**." The branches are swapped. This also fights the `accessibilityState={{ checked: value }}` the platform already announces. A blind user managing a privacy control is told the opposite of the truth — high-severity for a consent surface. Fix: `consent.granted ? copy.toggleA11yOn : copy.toggleA11yOff`.

**P1 — D2 (dark pattern / AI-tell): unequal weight on the first-capture prompt + comment that lies.**
`FirstCapturePrompt.tsx:39-50` renders accept as `tier="primary"` (filled accent, 52pt, `titleMd`/`onAccent`) and decline as `tier="tertiary"` (no fill, `label`/`secondary` tone) — per `Button.tsx:46-69`. The opt-in is visually emphasized over the decline, and the inline comment (`:18-19`) explicitly claims they are equal. §3.5 forbids dark patterns on consent; §3.6 auto-fails on a comment narrating a property the code contradicts. Fix: make decline `tier="secondary"` (equal-weight outline) or otherwise visually peer, and correct the comment. (The PrivacyScreen toggle itself is fine — default off, no nag.)

**P2 — S1: `granted` is derived from counts, not stored.**
`ConsentService.state` returns `granted = counts.total > 0` (`consent.py:42`). Consequences: (a) a user who opts in but has **zero** captures reads `granted=false` — the UI shows the toggle off even though their account-level intent is "on," and future captures from the client won't carry the opt-in because the screen believes it's off; (b) "account-level consent" has no durable home — it's inferred from per-record flags. Functionally safe for the privacy hard line (no over-emission), but it's a latent UX correctness bug and a conceptual gap vs the "account-level grant inherited by future captures" story the docstrings tell (`consent.py:9-13`). Consider a persisted account-level consent flag. Not a gate-blocker.

**P3 — T1: no component tests for the consent UI.**
Only the API binding is tested (`consent.test.ts`). PrivacyScreen states, the toggle's a11y label, and the prompt's button weighting are untested — which is exactly why D1/D2 slipped through. A render test asserting the spoken label matches `checked` would have caught D1.

---

## Bottom line

The **data path is correct and the privacy hard line genuinely holds** — one gate, no bypass, default-off proven on both sides with body-level assertions, revocation and erasure covering all three capture kinds. Security/Privacy, Architecture, Backend, and PMF all PASS. **Design and the Premium gate FAIL** on the consent UX: an inverted a11y label (D1) and a dark-pattern button-weight mismatch whose comment claims the opposite (D2). Both are small, surgical fixes; route back to the builder for D1+D2 (and ideally S1), then re-audit Design + Premium only.

---

## Re-audit (consent UX refine)

**Date:** 2026-06-18 · **Auditor lenses (re-scope):** Design (§3.4), Premium gate (§3.6, VETO), Security/Privacy (§3.5). **Verdict: PASS — gate cleared.** D1, D2, and P2 are all genuinely fixed at source; the privacy hard line did not regress.

### Re-run evidence (all green)

| Check | Result |
|---|---|
| `pytest -q` (api) | **148 passed** |
| `alembic upgrade head` | clean, 5 migrations apply (account-level added) |
| `alembic check` | **No new upgrade operations detected** (no drift) |
| `design-tokens build.mjs` | 146 tokens written |
| `mobile npm test` | **73 pass / 0 fail** |
| `tsc --noEmit` (mobile) | **0 errors** |
| hard-line subset (`-k 'non_consented or revoked …'`) | 14 passed — original zero-emission tests intact |

### D1 — a11y label inversion → FIXED (verified at source)
`PrivacyScreen.tsx:169` now reads `consent.granted ? copy.toggleA11yOn : copy.toggleA11yOff` — the branches match the copy: when sharing is ON the reader is handed `toggleA11yOn` ("…is on. Double tap to turn off."). `copy.ts:26-27` strings are state-accurate. `ConsentToggle.tsx:49` carries `accessibilityState={{ checked: value, disabled }}` (role=switch, true state). `onToggle` also announces the *resulting* state correctly (`PrivacyScreen.tsx:61-63`). The blind-user-told-the-opposite defect is gone. **No inversion remains.**

### D2 — dark pattern + lying comment → FIXED (verified at source)
`FirstCapturePrompt.tsx:39-50`: both accept and decline are now `tier="secondary"`. Per `Button.tsx:46,54-58,68-69`, secondary renders identically for both — 1.5pt accent outline, transparent fill, `label` variant, `accent` tone, `theme.tapTarget` height (no 52pt primary lift, no accent fill). Genuinely equal visual weight; nothing nudges the eye toward "yes." The false "equal weight"/"same prominence" comment is replaced with an accurate one ("the two buttons are visual peers… no pre-selected yes and no fill steering the eye"), matching `copy.ts:42-44`. The comment-contradicts-code AI-tell is gone.

### P2 — consent now ACCOUNT-LEVEL → FIXED (verified at source + tests)
- `User` model gained `training_consent` (default False), `training_consent_at`, `training_consent_revoked_at`, `consent_note`, plus a row-level `CheckConstraint` forbidding consent-active-while-revoked (`user.py`).
- Migration `d10a19c9ec6c_..._account_level_training_consent...` adds the columns NOT NULL with a temp `server_default=false` (safe backfill), then drops the default to match the Python-side default — `alembic check` stays clean.
- `ConsentService.state` reads `granted = user.training_consent` **directly** (consent.py), no longer `counts.total > 0`. Counts ride alongside as supplementary detail only.
- Captures stamp from the account: all three endpoints call `resolve_for_capture` (`api/scan.py:61`, `api/pregrade.py:99`, `api/authenticity.py:137`), which derives `training_consent` from the account state, never the wire.
- Revocation stops future emissions: `revoke_training_consent` clears the flag + stamps revocation; subsequent captures inherit not-consented.
- Proven by genuine TestClient tests: `test_grant_persists_with_zero_captures` (opted-in account, ZERO captures → `granted=true` on grant *and* re-read), and `test_revoked_account_stamps_new_captures_off_and_emits_nothing` (revoke → next scan emits nothing, `sink.examples == []`).

### Privacy hard line — NOT regressed
`test_non_consented_scan_emits_zero_examples` and `test_revoked_consent_record_never_emits` still pass within the 148; the single `_is_consented` gate in `emit.py` is unchanged. Non-consented/revoked → zero emission holds.

### Re-scored criteria

**Design (§3.4) — PASS (avg 3.0)**
| Criterion | Was | Now | Note |
|---|---|---|---|
| Bespoke, token-driven | 3 | 3 | unchanged |
| Real states | 3 | 3 | unchanged |
| Intentional motion + reduced-motion | 3 | 3 | unchanged |
| Accessibility (role=switch, 44pt, labels) | 1 | **3** | label now matches true state; announce-on-toggle correct |

**Premium / §3.6 gate (consent UX) — PASS · VETO LIFTED.** Zero AI-tells remain: the comment-contradicts-code tell is resolved, comments now describe *why* and match reality. Equal-weight buttons, honest copy, bespoke toggle, real states — would a top-tier studio ship this consent surface: honest yes.

**Security/Privacy (§3.5) — PASS (avg 3.0, up from 2.9).** No dark pattern on the consent ask (equal-weight peers, default-off, no nag). Account-level consent is now a durable, revocable source of truth with a row-level integrity constraint; the single emission gate is intact.

### Residual findings (non-blocking)
- **T1 (carried from P3):** still no render-level component tests for the consent UI (PrivacyScreen label↔checked, prompt button weighting). The source fixes are correct and the backend now has account-level coverage, but a render test asserting the spoken label tracks `checked` would lock D1 against future regression. Recommend filing as a follow-up; not a gate-blocker.

### Bottom line
**Gate cleared.** D1 (a11y inversion), D2 (dark-pattern + lying comment), and P2 (account-level consent) are genuinely fixed — confirmed by reading the diffed source, not just the green suite. Design and Premium now PASS; Security/Privacy strengthened. The privacy hard line did not regress. Only residual is the optional consent-UI render tests (T1).
