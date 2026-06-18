# Audit — P4.2 Mobile Rapid Stack Scan

**Auditor:** independent (design + premium gatekeeper + architecture + product/PMF)
**Date:** 2026-06-18
**Verdict:** **PASS** — Premium gate **PASS (no veto)**.

## Mechanical verification (tried to falsify)

| Check | Result |
|---|---|
| `packages/design-tokens && node build.mjs` | clean — 146 tokens |
| `apps/mobile && npm test` | **135 / 135 pass**, 0 fail |
| `apps/mobile && npx tsc --noEmit` | **0 errors** (no regression) |
| Hardcoded hex / rgba in `src/screens/rapid/` | **zero** |
| Emoji-as-decoration / lorem / TODO / `foo`/`temp`/`handleData` | **none** |
| Pokémon / Nintendo / real-IP card names | **none** (fictional sets: Origins Vault, Wildgrowth, Echo) |

The only literal numbers in styles are component-internal geometry (22pt checkbox, 20pt radio, ×N badge, absolute-fill `0`s, card aspect `0.714`) — layout spacing is fully `theme.space[*]`/`theme.radius[*]` driven. This is correct: intrinsic control geometry is not a spacing token.

## Hard-verification of the load-bearing claims

**Dedupe-merge honesty — PASS.** `stack.ts::applyCapture` (src/screens/rapid/stack.ts:66) finds an existing row by `canonicalId` and returns `effect:"merged"` with `captureRefs` appended, never a duplicate row; pendings/unreadables never merge. Proven by `__tests__/stack.test.ts:61` (merge → length 1, count 2) and the purity test (:87). Mirrors the backend identity dedupe in batch_scan.py:55-68. The count badge (StripThumb.tsx:80, ResolvedRow.tsx:71) is gated on `count > 1`. **Honest.**

**Confirm-at-end correctness — PASS.** `selectedAdditions` (stack.ts:165) only banks `needs_confirmation` cards whose pick is non-null (`if (pick == null) continue;`), so a high-value variant is never silently banked — proven by stack.test.ts:207. Resolved cards are bulk-addable and default-selected (RapidReviewScreen.tsx:81). Quota is rendered via `QuotaCard` (RapidReviewScreen.tsx:261) on `amberSoft`/`amber` tokens (the documented "never red" caution surface, tokens.json:76-78), with the free-tier rationale + reset + Collector+ path in `quotaHint` (copy.ts:70). Unrecognized offers `Re-capture` (RapidReviewScreen.tsx:191). **Correct.**

**ID+value-only boundary — PASS, explicit and intentional.** Stated up front (RAPID_SUBTITLE, copy.ts:10), reinforced per resolved row by the "Grade / Check authenticity ›" affordance (ResolvedRow.tsx:100) that re-enters the single guided capture (`onGrade` → `router.replace("/")`, rapid-review.tsx:44). The batch model has *no* grade/auth fields by construction (models.ts:77-108) — a typed boundary, not a hidden gap.

**Architecture / contract fidelity — PASS.** `types.ts:254-300` mirrors batch_scan.py field-for-field (snake_case wire). `mapping.ts::mapBatchItem` is a real discriminated-union switch with a loud `MappingError` on unknown outcomes and on malformed resolved/confirmation payloads (mapping.ts:120,126,141) — fails at the boundary rather than dropping a flipped card. Fixture mode (`batchScanFixture`, client.ts:309) and http mode (client.ts:176) both present; fixture `STACK_BATCH` exercises all four outcomes incl. the count-2 dedupe and a €732.60 confirm delta, and its refs line up with `useMockStackCaptures` so live preview and authoritative review never contradict. Flow wiring (ScanFlowProvider: `runBatchScan`/`bulkAddToVault`/`resetBatch`) holds the result so back-nav never re-runs recognition; `bulkAddToVault` bumps the Vault revision once and counts per-card failures out instead of aborting the lot. Reuses single-scan `mapChoice`/`ScanChoice`/`identitySubline`/`variantLabel`/`FoilSurface`/`ValueText` — no copy-paste drift.

## Per-criterion scores

### §3.1 Product / PMF — avg 3.0
- ICP need (rapid stack triage, ID+value): **3**
- Honest framing (delta + "no € comp", quota calm, never silent bank): **3**
- Freemium/quota boundary respected (8/day, charged/remaining/rejected surfaced honestly): **3**
- No scope creep (ID+value only, grade re-enters guided): **3**

### §3.2 Architecture — avg 2.75
- Fits system design, ML stage swappable behind fixture/http: **3**
- Module boundaries, pure `stack.ts` never re-implemented in screen: **3**
- Data-capture/consent loop: **2** (consent rides the existing single-scan `trainingConsent`; not surfaced in the batch UI — acceptable for ID+value, noted below)
- Traceable decisions (contract docstrings cite master plan §7/§6): **3**

### §3.4 Frontend / Design — avg 2.9
- Bespoke, token-driven, zero framework chrome: **3** (custom filmstrip, count pill, ×N badges, checkbox vs radio geometry distinct by intent)
- Custom components matching Foil Vault: **3**
- Intentional motion, `prefers-reduced-motion`: **3** (per-flip slide+settle once; reduced-motion lands settled; outcome-specific haptics; debounced total announce)
- Real empty/loading/error states + a11y: **3** (skeleton loading, error w/ SR announce + "nothing added", empty filmstrip instruction, "nothing read cleanly" terminal state; SR announces add/merge/miss/running-total; tabular € via ValueText; locale de-DE currency)

### §3.6 Premium / Not-Generic gate — **PASS, zero AI-tells**
No generic/stock look, no centered-everything (review is left-aligned list; only true empty/error bodies center, correctly), no lorem, no over-narration, no dead code/unused params, no emoji-decoration, no boilerplate voice, consistent house style across all 10 files, domain-precise naming (`StripEntry`, `applyCapture`, `reviewKey`, `VaultAddition`). Unglamorous details present: focus/pressed states, hairline borders, SR announce on error, debounced burst announce, float-drift rounding test.

## Findings (prioritized, non-blocking)

1. **[low] Resolved-section subline plurality.** RapidReviewScreen.tsx:195 renders `{n} flips didn't read.` under *Couldn't read* with a hardcoded `flips` — singular case ("1 flips didn't read") is ungrammatical. The quota copy pluralizes correctly via `quotaHint`; mirror that here. (Cosmetic, SR + visual.)
2. **[low] `useMockStackCaptures.remaining` exported but only `done` consumed** (useMockStackCaptures.ts:55). `remaining` is part of the documented stand-in contract, so not dead — but if it stays unused when the camera lands, drop it. Watch-item, not a defect.
3. **[info] Consent not re-surfaced in batch UI** (§3.2 above). Batch inherits the session `trainingConsent`; for an ID+value pass with no image upload of gradeable detail this is defensible, but worth an ADR line so the moat's consent loop stays traceable when real captures replace the mock.

None of these reach the ≥2 floor on any criterion; every criterion is ≥2 and every lens averages ≥2.5.

## Gate

**PASS.** Commit and mark P4.2 done. File finding #1 as a quick refine (one-line plural fix); #2/#3 as watch-items at the camera-integration boundary.

---
## Gate resolution (orchestrator, 2026-06-18)
PASS — Design/Premium/Architecture/PMF all clear, no veto. Dedupe-merge, confirm-at-end (no undecided card banked), the explicit ID+value-only boundary, and the discriminated batch binding all independently verified; 135 tests, tsc 0. Finding #1 (visible "1 flips" grammar) FIXED — added count-aware unreadCaption() helper matching the existing pluralization pattern; tsc 0 + 135 tests still green. #2 (unused remaining export) + #3 (consent-in-batch ADR line) filed to #11. **GATE: PASS — merged.**
