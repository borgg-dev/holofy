# Audit — P2.2 Mobile Pre-grade Flow

**Slice:** Guided multi-angle capture → honest pre-grade gauge (range + sub-scores), mobile.
**Auditor:** independent design/premium/product/architecture lens (did not build this).
**Date:** 2026-06-18
**Verdict:** **PASS** — Premium gate **PASS (no veto)**. Honest-framing hard gate **clears**.

---

## How verified (no device / no native toolchain)

- `packages/design-tokens && node build.mjs` → clean ("Wrote tokens.ts, tokens.css, dist/ from 146 tokens").
- `apps/mobile && npm test` (custom `--experimental-strip-types` resolver) → **64/64 pass**, 0 fail. (A bare `node --test` fails on extensionless TS imports — that is a harness invocation error, not a code defect; the project's `test` script is the supported entrypoint.)
- `npx tsc --noEmit` → 7 errors, **all in non-P2.2 code** (see Pre-existing debt). Every P2.2-authored/edited file is tsc-clean.
- Static falsification grep: hardcoded hex, emoji, lorem, single-grade render paths, `.grade` field access, theme-token resolution.

---

## §3.1 Product / PMF — PASS (avg 2.9)

| Criterion | Score | Notes |
|---|---|---|
| Maps to ICP need (worth grading?) | 3 | The decision is driven by `pAtLeast` ("70% chance it's a 9+, worth the fee"), not a band midpoint — `gauge.ts:21-28`. This is the collector's actual decision figure. |
| **Honest framing (hard gate)** | 3 | See dedicated section below — clears decisively. |
| Quota/freemium boundary | 2 | Error copy states "Nothing was charged" (`copy.ts:52`); retake never consumes a grade. The full paywall/"2 of 3 this month" state from gauge-spec §54 is **not** built (deferred), which is acceptable for this slice but should be tracked. |
| No scope creep | 3 | `onLogGrade`/`onWhatAffects` are stubbed with honest `// P2.3` markers (`app/pregrade.tsx:35-40`), not half-built. |

## §3.2 Architecture — PASS (avg 2.9)

| Criterion | Score | Notes |
|---|---|---|
| Fits system design; ML stages swappable | 3 | Provenance derives from a `MEASURED_AXES` set + `LIMITED_CONFIDENCE` threshold (`mapping.ts:136-144`) — centering `measured`, bought axes `estimated`, low-confidence `limited`. The buy→build seam is honored in the UI provenance, matching the spike. |
| Module boundaries / no leaky coupling | 3 | Clean wire→model→view-logic layering: `types.ts` (snake_case wire) → `mapping.ts` (boundary parse, throws `MappingError`) → `models.ts` (discriminated union) → pure `gauge.ts` (renderer-free, unit-tested). Screens never see wire shapes. |
| Data-capture/consent loop | 2 | "Log my real grade later" is the moat hook, present and consent-framed in copy/hint, but wired to a P2.3 stub. Correct for this slice. |
| Contract match to `grading.py` | 3 | `WirePregradeResponse` reproduces the Pydantic discriminated union field-for-field (`estimated`→probability+sub_scores+confidence; `retake`→reasons; disclaimer always present). Both fixture and HTTP clients route through the same `mapPregrade`. `/pregrade` POST body matches `PregradeRequest` (`capture_ref`/`card_id`). |

**Flow wiring** is coherent: `reveal → /pregrade-capture (GuidedCapture) → runPregrade → /pregrade (gauge|retake)`. Cold-land guards (`revealChoice` null → redirect) on both routes. Retake's re-scan and gauge back both route into a fresh capture, so the "cleaner shot" loop terminates somewhere real.

## §3.4 Frontend / Design — PASS (avg 2.8)

| Criterion | Score | Notes |
|---|---|---|
| Bespoke, token-driven, no stock chrome | 3 | The gauge is a hand-built 200° SVG arc with a luminous violet→teal **band** painted between two grades (`GaugeArc.tsx`) — not a progress bar, not a needle. Zero hardcoded hex in `src/screens/pregrade/` (grep clean). All color/space/radius via `theme.*`. |
| Custom components / Foil Vault consistency | 3 | Reuses the system's `ScanFrame`, `QualityChip`, `CoachingToast`, `Shutter`, `Skeleton`, `Screen ground="vault"` — one house voice with the scan flow. The `AngleProgress` pip row reads as an instrument scale, not a generic carousel. |
| Intentional motion + reduced-motion | 3 | Arc/band bloom (`GaugeArc.tsx:52-65`), staggered 60ms meter fills (`SubScoreRow.tsx:38-43`), one lock haptic. `useReduceMotion()` renders every animated value in final state at once — verified in both components. |
| Real states + a11y + alignment | 3 | Computing (honest staged skeleton, no fake progress bar), Error (credit-not-charged), Retake (coaching), Surface-limited (amber caveat + widened-range copy). SR announces range+verdict+confidence (`PregradeGaugeScreen.tsx:55-57`); sub-scores announce value/max/provenance; numerals use `tabular`; decorative SVG hidden from SR. No centered-everything (left-aligned reading column; only confidence line + a balanced topbar are centered, intentionally). |

## §3.6 Premium / Not-Generic gate — **PASS · NO VETO**

Zero AI-tells found:
- No generic/stock look, no default-library chrome, no centered-everything, **no lorem/placeholder** (grep clean). Copy is domain-precise product writing ("rake the light from the right to read the other half of the surface", `capturePlan.ts:60`).
- Comments explain **why**, not what (e.g. the `np.diff` provenance note carried into `capturePlan.ts`; the `pAtLeast` risk-posture rationale in `gauge.ts:18-21`).
- No dead code, no `foo`/`temp`/`handleData` naming, no speculative abstraction. Domain naming throughout (`firstFailing`, `modalGrade`, `axisProvenance`).
- **No emoji-as-decoration**, no em-dash hype copy.
- Unglamorous polish present: focus/lock haptic edge, refuse-to-grade microcopy, credit-not-charged reassurance, toast cleanup on unmount, NaN-guarded clamps.

---

## HONEST FRAMING — hard gate — **CLEARS**

Tried hard to falsify; could not find a path that presents an absolute grade as "the grade":

1. **No single grade anywhere in the type system.** `GradeProbabilityRange` (model + wire) has no `grade` field; a regression test explicitly asserts `range.grade === undefined` (`pregrade.test.ts:20-27`). The composite is `likelyLow/likelyHigh/atLeast/pAtLeast`.
2. **Headline is always a band.** `verdictLine` / `VerdictLine` render `"Likely 8–9 · Worth grading"`; a one-grade band collapses to `"9"` but is still framed "Likely …", never "the grade" (`gauge.ts:30-40`, tested at `gauge.test.ts:48-59`).
3. **The one modal numeral is correctly hedged.** `GaugeArc.tsx:140` renders `formatScore(modal)` at the band core. It (a) sits *inside* the painted band, (b) carries a `"modal"` caption directly beneath it (`GAUGE_MODAL_LABEL`), and (c) is `accessibilityElementsHidden` so the SR user hears only the range. This matches gauge-spec §2 ("a brighter core at the modal grade") while staying inside the honest frame. **Minor finding (not a veto):** the modal numeral is set in `displayMd` — the same weight as the verdict band line — so visually it is prominent. It is never labelled "the grade" and is always wrapped by the band + caption, so it does not breach the gate, but a designer could argue for a smaller/dimmer treatment to remove any chance a glancing user reads it as a point grade. Recommend down-weighting in P2.3 polish; does not block.
4. **Low confidence → amber/neutral, never red.** `verdictFor` only emits `worth`/`borderline`/`hold`; "hold" is `textSecondary` (neutral), "borderline" is `amber` (`PregradeGaugeScreen.tsx:149-154`), tested at `gauge.test.ts:29-46`. `theme.color.errorRed` exists in the palette but is referenced **nowhere** in the pregrade flow (verified). Surface-limited/retake use amber + calm coaching, never alarm.
5. **Disclaimer + non-affiliation present and prominent.** Persistent, non-dismissible footer in the reading order with a top rule (`PregradeGaugeScreen.tsx:124-131`), combining the schema `disclaimer` with `NON_AFFILIATION` (covers PSA/CGC/BGS **and** Nintendo/Pokémon IP — `copy.ts:38-39`). Also announced in the retake SR string.

## Guided capture is real, not decorative — **CONFIRMED**

The capture coaches the exact failures the spike named, not a generic "hold steady":
- **Skew/alignment** is first-class — `CaptureSignals.skew`, surfaced first via `chipOrderFor` for the square-on angles (`capturePlan.ts:38-49, 83-89`), with copy "shoot straight down so all four borders stay parallel — this is what makes centering measurable." Directly answers the spike's "perspective/skew is the single biggest dependency."
- **Glare** is the primary signal for **two opposite raking-light passes** (`surface-rake-left`/`-right`), with copy that names why ("reveals scratches a flat shot hides" / "read the other half"). Matches the spike's glare + multi-angle-median mitigation.
- **Refuse/retake path is real:** the shutter refuses a sub-threshold shot (`GuidedCaptureScreen.tsx:75-87`), emitting a per-signal coaching line via `refuseMessage`; a too-poor bundle resolves to the schema's `retake` status → `RetakeScreen` coaches and routes back into capture. The quality stream is mock-driven (honestly documented in `useGuidedCapture.ts` as the seam the on-device detector slots into), but the lock/refuse/advance/complete state machine is real.

---

## Pre-existing tech debt (flagged for tracking — does NOT fail P2.2)

`npx tsc --noEmit` reports **7 errors, none introduced by P2.2**. Confirmed via git (P2.2 is uncommitted on top of `a3dd97a`):

| # | Location | Error | Pre-existing? |
|---|---|---|---|
| 1-3 | `src/api/fixtures.ts:78,88,89` | `WirePriceQuote \| undefined` not assignable (no-uncheckedIndexedAccess on `PRICES[...]`) | **Yes** — these `PRICES["origins-8"]` accesses are unchanged in `HEAD` (lines 73/83/84 there). P2.2 only appended the pregrade fixture block, which is type-clean. |
| 4 | `src/screens/confirm/ConfirmScreen.tsx:119` | array style not assignable to `ViewStyle` | **Yes** — file not touched by P2.2. |
| 5-7 | `src/screens/vault/VaultScreen.tsx:151,186,209` | array-style typing + `"titleMd"` not a valid `Text` variant | **Yes** — file not touched by P2.2. |

These are real and should be fixed (the `PRICES` indexing ones are trivial `!`/null-coalesce; the array-style ones are a `StyleProp<ViewStyle>` vs `ViewStyle` typing nit; `"titleMd"` looks like a stale variant name). File as a standalone tech-debt cleanup task. **No P2.2 file contributes a single tsc error.**

---

## Prioritized findings

1. *(polish, non-blocking)* `GaugeArc.tsx:140` — the modal numeral uses `displayMd`, equal in weight to the verdict line. Down-weight (smaller/dimmer) so it cannot be glance-read as a point grade. Honest-framing gate still clears (band + "modal" caption + SR-hidden).
2. *(tracking)* Fix the 7 pre-existing tsc errors in `fixtures.ts` / `ConfirmScreen.tsx` / `VaultScreen.tsx` as a separate task — they were not introduced here but keep `typecheck` red.
3. *(scope note)* Out-of-credits / paywall state (gauge-spec §54) is not built — fine for this slice; confirm it's on the P2.3+ backlog.

**Gate result: PASS. Premium gate not vetoed. Ship.**

---
## Gate resolution (orchestrator, 2026-06-18)
PASS — Design/Premium/PMF(honest-framing)/Architecture all clear; no veto. Honest-framing independently falsified-then-confirmed: no `grade` field in the type system, headline is always a band, modal numeral is band-internal + captioned + SR-hidden, low confidence is amber-never-red, disclaimer + non-affiliation persistent. Non-blocking: down-weight the modal numeral's type style (filed #11). **Confirmed pre-existing tsc debt** (7 errors: fixtures.ts PRICES indexing, ConfirmScreen, VaultScreen — all pre-date P2.2, zero introduced here) → filed as a dedicated cleanup task to clear before Phase 2 closes. **GATE: PASS — merged.**
