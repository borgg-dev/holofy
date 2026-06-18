# P3.2 Audit — Authenticity (mobile)

**Auditor:** independent (design lens + Premium/Not-Generic gatekeeper + security/privacy §3.5 + product §3.1)
**Date:** 2026-06-18
**Artifact:** `apps/mobile/src/screens/authenticity/` + `app/authenticity.tsx` / `app/authenticity-capture.tsx` + `src/api` authenticity binding + edits to `app/reveal.tsx`, `src/flow/ScanFlowProvider.tsx`

## Verdict

**PASS — Premium gate: PASS (no veto).** No defamation/no-verdict violation found; F2 confidence separation honored; no red anywhere; bespoke shield; token-driven; full state coverage; clean architecture. Two minor, non-blocking findings (P2/P3) below.

Build/test gates (all green):
- `packages/design-tokens && node build.mjs` → wrote 146 tokens, OK.
- `apps/mobile && npx tsc --noEmit` → exit 0 (no regression).
- `apps/mobile && npm test` → **tests 106 / pass 106 / fail 0**.

---

## Hard gates (tried to falsify each)

### NO-VERDICT / DEFAMATION — PASS (hard gate clears)
- The band→presentation table (`src/screens/authenticity/band.ts:36-55`) is a *closed* `Record<RiskBand, …>` over exactly 3 bands. Every headline is calm: `strongSignals` → "No counterfeit indicators", `inconclusive` → "We couldn't read enough to say", `elevatedRisk` → "Some signals don't match". The most-adverse output is amber + "we recommend professional authentication" — never red, never an accusation. There is no code path that renders a 4th/binary band.
- **Only sanctioned uses of "counterfeit":** the negating headline "No counterfeit indicators" (`band.ts:39`), the self-negating disclaimer ("not a determination that a card is genuine or counterfeit", `fixtures.ts:31`), the generic not-assessed line "Counterfeiters target cards worth faking" (`copy.ts:55` — a category statement, not an accusation about *this* card/seller), and comments. No positive "this is a counterfeit"/"fake"/"genuine" string anywhere. Confirmed by grep and by the wire/view tests (`band.test.ts:65-74`, `authenticity.test.ts:126-143`) which strip the negation and assert nothing else matches `/counterfeit|fake|genuine/`.
- **Falsification attempt — accusatory payload:** the only server-controlled free text that reaches the UI is `signal.detail`, rendered verbatim in `SignalRow.tsx:43-45` and `signalA11y` (`band.ts:141-145`). The band, tone, headline, and recommendation are all client-derived from the typed enum, so a hostile payload cannot promote the headline past `elevatedRisk` or flip tone to red. The schema (`authenticity.py`) has no `is_fake`/`is_genuine` field to render from. **No constructible accusatory/binary verdict.** (Residual note: see Finding 1 — `detail` is the one un-sanitized text surface.)
- The disclaimer is persistent and in reading order on every terminal screen (`VerdictScreen.tsx:151-160`, `StatusScreens` via `Disclaimer()`), never fine print/dismissible.

### SEPARATED CONFIDENCE (F2 from P3.1) — PASS
- `confidence` is rendered **only** as evidence/read quality, in its own bordered region with its own heading ("Evidence quality"), a neutral grey meter (`theme.color.textSecondary`, not an accent), and the line "we could read the card at ~X% clarity" (`VerdictScreen.tsx:118-142`, `band.ts:74-83`). It never shares a sentence with the band.
- The SR announcement keeps the three regions explicitly separate and ordered — band → recommendation → "Evidence quality, separately: a {label} read…" (`band.ts:127-138`). Test `band.test.ts:90-94` asserts the evidence line never contains `risk|authentic|fake|genuine|sure`.
- The region's `accessibilityLabel` is prefixed "Evidence quality, separate from the result:" (`VerdictScreen.tsx:131`). The meter itself is SR-hidden so the percent isn't double-announced.

### No red anywhere — PASS
- Authenticity tones are only `reassuring` (vaultTeal) / `caution` (amber) (`band.ts:22-23`). `errorRed` exists in the theme but is **not referenced** anywhere under `authenticity/` (grep empty).
- `unreadable` renders as a neutral grey "Couldn't read" (`band.ts:111`, `SignalRow.tsx:56` → `textTertiary`/`bgRaised`), explicitly not a strike. `deviation` renders amber "Doesn't match", not red. Tests `band.test.ts:59`, `:114-116` lock this.

---

## Per-criterion scores

### §3.4 Frontend / Design — avg 2.75 (PASS)
| Criterion | Score | Note |
|---|---|---|
| Bespoke, token-driven | **3** | Custom shield SVG (crest + vault crossbar, `ShieldMark.tsx:27-28`), zero hardcoded hex/spacing in screens (grep clean), all color/space/radius from `useTheme`. |
| Custom components, Foil Vault fit | **3** | Reuses pregrade's `ScanFrame`/`QualityChip`/`Shutter`/`CoachingToast`, German `Intl` currency matching reveal, one consistent house voice. |
| Intentional motion + reduced-motion | **3** | Shield edge-draw + fill bloom on a bezier; `useReduceMotion` renders it settled (`ShieldMark.tsx:39-50`). Haptic on lock edge gated on reduce-motion (`GuidedCaptureScreen.tsx:56`). |
| States + a11y + alignment | **2** | All five states present (assessed/retake/notAssessed/screening/error). SR announcements, 44pt `tapTarget`, progressbar role, color-never-alone (state words paired). Minor: see Finding 2 (percent not tabular). Not centered-everything — verdict is left-aligned, deliberate. |

### §3.6 Premium / Not-Generic gate — PASS (zero AI-tells, no veto)
- No stock checkmark/badge (the design *avoids* the "authentic ✓" stamp by intent, `ShieldMark.tsx:26`). No centered-everything. No lorem/placeholder/TODO/FIXME/dead code (grep clean; the one "placeholder" hit is a comment asserting the copy is *not* placeholder). No `foo`/`temp`/`handleData` naming. No emoji-as-decoration (the single `✓` is inside an explanatory comment). Comments explain *why* (defamation rules, capture↔ML rationale), not *what*. Domain-precise naming (`bandPresentation`, `evidenceQuality`, `chipOrderFor`). House style consistent with pregrade. **Would a top-tier studio ship this? Honest yes.**

### §3.5 Security & Privacy — avg 3.0 (PASS)
| Criterion | Score | Note |
|---|---|---|
| No binary public "FAKE" verdict | **3** | Hard gate clears — see above. Guardrail encoded in types, not just copy. |
| Consent honored | **3** | `trainingConsent` plumbed through `runAuthenticity` → `api.authenticity` (`ScanFlowProvider.tsx:180`, `client.ts:197-205`); defaults off; account-level per schema. |
| Data minimization | **3** | Request carries `capture_ref` + `card_id` only, never bytes (`client.ts:200-204`, mirrors schema §6). |

### §3.1 Product / PMF — avg 2.75 (PASS)
| Criterion | Score | Note |
|---|---|---|
| Maps to ICP need | **3** | The master-plan §6 shield/amber authenticity moment, gated on a resolved high-value card. |
| Honest framing (ranges + confidence, no absolutes) | **3** | Band not boolean; "screening signal, not a guarantee" (`band.ts:41`); retake refuses to flag on an unreadable capture; not-assessed framed "not a red flag, just not needed" (`copy.ts:55`). |
| Quota/value boundary | **2** | Value-threshold gate respected (notAssessed path + `referenceValueEur` framing). Credit-not-consumed-on-error messaged (`copy.ts:38`). |
| No scope creep | **3** | The pro-authentication out-link is correctly deferred to P3.3 (stub, not built early). |

---

## Architecture

- App-side binding mirrors `apps/api/app/schemas/authenticity.py` field-for-field; wire→model mapping in `mapping.ts:194-234` is a discriminated union on `status` (assessed | retake | notAssessed) with `MappingError` guards (assessed-without-assessment, assessed-without-signals, refuse-without-reasons). Snake→camel band translation isolated to one table.
- Fixture + http modes both present (`client.ts:197` http POST, `:302` fixture via `authenticityFixtureFor`), five fixtures covering all outcomes, all card data Holofy-original IP ("Emberwyrm Sovereign / Origins Vault", `fixtures.ts:5,72`).
- Flow wiring coherent: `reveal.tsx:47` → `/authenticity-capture` → guided capture → `runAuthenticity` → `/authenticity` route switches on flow state then on result status (`app/authenticity.tsx:27-57`). Cold-land redirects guard both routes. Cleanly reuses the pregrade capture pattern (shared `CaptureSignals`, same chip/lock/refuse choreography).

---

## Prioritized findings (none blocking)

**F1 (P2 — security, follow-up not refine):** `signal.detail` is the single server-controlled free-text string rendered verbatim to the user (`SignalRow.tsx:43`, `band.ts:144`). The type system blocks an accusatory *band/headline*, but a malicious or buggy backend could emit an accusatory sentence in `detail` (e.g. naming a seller). The defamation guarantee currently rests on the backend's discipline for this one field. Recommend a server-side `detail` content contract/lint (observational-only, no seller references) — file against the backend, not P3.2. Does not gate this slice.

**F2 (P3 — design polish):** The evidence-quality percent ("~83% clarity", `band.ts:82`) and the SR percent are plain text, not rendered with the tabular-figures treatment used elsewhere for numerals. Low impact (single inline value, not a column), but for house-style consistency consider the tabular variant. `VerdictScreen.tsx:139`.

**F3 (informational):** `onAuthenticate` in `app/authenticity.tsx:39-41` is an intentional empty handler with a `// P3.3` marker — the "Find a professional authenticator" CTA is wired but inert until P3.3. Correct scoping (not dead code), but the primary CTA is currently a no-op in the build; ensure P3.3 lands before this screen is demoed as complete.

**Note (cleared, not a finding):** the Nintendo / The Pokémon Company mention (`copy.ts:27`) is a *non-affiliation disclaimer*, the legally protective use — not appropriated IP. All card content is Holofy-original. No Pokémon/Nintendo IP violation.

---
## Gate resolution (orchestrator, 2026-06-18)
PASS — Design/Premium/Security(no-verdict)/PMF(honest-framing) all clear, no veto. Falsification attempts could not construct an accusatory/binary output (band/tone/headline are client-derived from a closed 3-band enum; no fake/genuine field exists). F2 separated-confidence honored (evidence-quality region, never conflated with the band). No red. 106 tests, tsc 0. Non-blocking findings filed to #11: F1 (backend signal.detail free-text needs a non-accusatory content contract before the real provider integrates — defamation-adjacent, worth doing at integration), F2 (evidence % tabular figures), F3 (authenticator-CTA stub). **GATE: PASS — merged.**
