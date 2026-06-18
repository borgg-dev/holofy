# Audit — P1.4 Mobile half (Foil reveal · Confirm · Vault)

**Auditor:** independent design/premium/architecture lens
**Date:** 2026-06-18
**Scope:** `apps/mobile/` — `src/screens/{reveal,confirm,vault,shared}`, `src/flow/ScanFlowProvider.tsx`, new components (FoilCard, CountUpValue, Button, Skeleton, TrendPill), `src/api/`, expo-router wiring (`app/`), edits to `ScanScreen.tsx`.
**Verdict:** **PREMIUM GATE — VETO (conditional).** One hard blocker (Pokémon/Nintendo IP throughout the demo data). Everything else clears the bar; several criteria are genuinely excellent. Fix the IP and this is a pass.

---

## Verifiable checks (no device / no node_modules — same constraint as the builder)

| Check | Result |
|---|---|
| `cd packages/design-tokens && node build.mjs` | **Clean.** `Wrote tokens.ts, tokens.css, and dist/ from 146 tokens.` EXIT 0 |
| `npm test` (node `--test`, deps not required) | **26/26 pass, 0 fail, 0 skipped.** Builder's claim holds. |
| Hardcoded hex in screens/flow/components | **4 found** — all justified (see Findings F4). Not the "zero" claim taken literally, but none are stray product colors. |
| Raw spacing/duration literals | Layout spacing uses `theme.space[*]` consistently. Remaining raw numbers are bespoke control geometry (22pt radio, 5pt busy dots, sheen width) or animation micro-timings — defensible (F5). |
| Pokémon/Nintendo IP | **PRESENT — VETO trigger (F1).** |
| € never fabricated when missing | **Honored.** `NoPriceState` + "No € comp" everywhere; `trendFromQuote` returns null without `avg30`. |
| Trend-down amber-not-red | **Honored.** `TrendPill` maps `down → theme.color.amber`; `errorRed` exists but is never used for a price dip. |
| Pre-grade framed as estimate | Copy: "estimate a grade" (GRADE_HINT); action is "Pre-grade this card". Honest. (The gauge itself is P2.) |
| Confirm renders top-2 + € delta | **Yes** — `choices.slice(0,2)`, per-choice `ValueText`, delta in the header sentence. |
| Flow wiring scan→reveal\|confirm→vault | **Coherent**, with deep-link redirects back to `/` when state is absent. |

---

## Per-criterion scores

### §3.4 Frontend / Design
| Criterion | Score | Note |
|---|---|---|
| Bespoke, zero default-framework chrome | **3** | Headerless Stack; every screen owns its chrome. No RN `<Button>`/default nav anywhere. Single `Text` primitive bound to the type scale; `ValueText` is the only money path (Intl). |
| Custom components, Foil Vault system | **3** | FoilCard reveal (SVG sweep + specular sheen + 3D rest pose), FoilSurface foil-edge scarcity, vault-teal glow header. Reads as a designed system, not a stock kit. |
| Intentional motion + `prefers-reduced-motion` | **3** | Count-up odometer, foil bloom 0.22→0.5→0.18, sheen travel, entrance scale. Reduced-motion is plumbed end-to-end (`useReduceMotion`) and renders settled state instantly in FoilCard, CountUpValue, and RevealScreen's action gate. |
| Empty / loading / error / a11y / locale | **3** | Vault has real loading (skeletons), error (retry), empty states. de-DE Intl currency throughout. SR labels on every interactive element (46 a11y props), radio group semantics on Confirm, polite live-region announcements, 44pt tap targets via `theme.tapTarget`, real minus glyph "−". |

**Lens avg ≈ 3.0 — PASS.**

### §3.6 Premium / Not-Generic gate
Every criterion ≥2 on the design lens. AI-tells sweep:
- Generic/stock look — **none.** Centered-everything — **avoided**; reveal value block + identity are deliberately left-aligned (`alignSelf: "stretch"`, `valueBlock`/`identity` left), only genuine "calm money" surfaces (empty/error) center. Builder's claim verified.
- Lorem/placeholder copy — **none in product UI.** "Placeholder" hits are code comments describing the camera-feed stand-in, not shipped copy.
- Emoji-as-decoration — **none.**
- Over-commenting (what-not-why) — comments are consistently *why* (e.g. "a fixed 10px gap reads tighter than the scale's 12, by design"; "down is amber, never red"). Good restraint.
- Dead code / unused exports — **none found.** `reward` tone is wired through `Text.tsx`; every `components/index.ts` export is consumed; CountUpValue's `tone`/`durationMs` are real seams.
- Inconsistent house style — **consistent** across all new files (token access, comment voice, naming).

**The one AI-tell / gate failure is not stylistic — it's the IP (F1), which the gate's "would a top-tier studio ship this?" cannot answer yes to with live trademarks in it.** **GATE: VETO until F1 resolved.** Absent F1 this would be a clean pass.

### §3.2 Architecture
| Criterion | Score | Note |
|---|---|---|
| Fits system design; ML stages swappable | **3** | Fixture backend speaks the *wire* shape (snake_case, string money) and flows through the same `mapping.ts` as a real response — `mode="http"` + baseUrl is the only switch (`app/_layout.tsx:32`). Buy→build seam intact. |
| Module boundaries / no leaky coupling | **3** | `@/theme` is the single token entry; `tokens.ts` is the only reach into the package. Flow state lives in one context, not URL-serialized. Pure, framework-free `shared/format.ts` is unit-tested. |
| Data-capture/consent loop | **n/a this slice** | No user content persisted here; consent loop is a later slice. |
| Decisions traceable | **2** | Rationale lives in dense header comments rather than ADRs; acceptable at this altitude. |

**Lens avg ≈ 2.9 — PASS.**

---

## Findings (prioritized)

### F1 — BLOCKER / VETO: Pokémon & Nintendo IP throughout the demo data
`src/api/fixtures.ts:57-60,63-66,82-83,96-113,125` — "Charizard", "Blastoise", "Venusaur", "Base Set", "Base Set 2", "Jungle", collector numbers `4/102`, `2/102`, `15/64`. These are live Nintendo/The Pokémon Company trademarks and rendered on the most brand-defining screens (FoilCard face, Confirm choices, Vault rows).
- The brief lists "NO Pokémon/Nintendo IP" as an explicit verification item; the charter's §5.2 names brand/IP as a hard launch gate.
- **Context, not an excuse:** the mobile fixtures faithfully mirror `apps/api/app/providers/recognition/mock.py:25-55`, which already carries the same IP. So this is a *project-wide* mock-data decision the P1.4 builder inherited — but it is now also shipping in the mobile demo build, so it must be remediated here and filed against the API mock too.
- **Fix:** replace with neutral invented cards (e.g. a fictional set/creature line) that still preserve the load-bearing property — two near-identical variants whose € values diverge ~30× (the reason Confirm exists). The €757.10 vs €24.50 split must survive the rename. Keep API and mobile fixtures in sync.

### F2 — Minor: `listings={312}` hardcoded at the route, not derived
`app/reveal.tsx:22`. The reveal's trend line shows "… · 312 listings" from a literal, while RevealScreen is wired to take it as a prop and the quote carries market depth. The fixture `PriceQuote` has no listing count, so the route invents one. Honest-framing-adjacent: a fabricated listing count is a (small) invented number on the value screen. Either thread a real `listings` through the quote or drop the count from the line until it's real.

### F3 — Minor: `errorRed` token defined but unused
`theme.ts:24` (`errorRed`) is exported but no screen references it. Not dead-code in the strict sense (it's a token, and a future error microcopy surface may want it), but worth a note — currently the only error surface (Vault) uses neutral tones. Acceptable; flag only.

### F4 — Hex literals (all justified, listed for traceability)
- `FoilCard.tsx:157` `shadowColor: "#6C3CE0"` — equals `elevation.foil` token rgba(108,60,224,…); RN `shadowColor` can't take the token's composite rgba string, so the violet is extracted. Defensible; a `tokens.color.brand.holoViolet`-derived constant would be marginally cleaner.
- `FoilSurface.tsx:57` `shadowColor: "#000"` — standard elevation black; fine.
- `CameraPreview.tsx:13-14` `MOCK_TABLE_DARK/LIT` — explicitly a stand-in for the live camera feed (pre-expo-camera). Acceptable as scaffolding; ensure it's gone when expo-camera lands.

### F5 — Raw numerics (defensible, noted)
Bespoke control geometry kept as component constants rather than spacing tokens: 22pt radio (`ConfirmScreen.tsx:180`), `choicePrice` gap 10 (`:177`, commented as intentional), busy-dot sizes (`Button.tsx:96-98`), sheen width / facePlate margins (`FoilCard.tsx`), the 220pt glow circle (`VaultScreen.tsx:267-269`), shake/scan animation durations. These are correctly *not* layout spacing; leaving them as local constants is the right call. No action.

---

## Bottom line
This is genuinely shipping-premium Foil Vault, not competent-but-generic: bespoke reveal motion, honest money framing (no fabricated €, amber dips, no-price state), real loading/empty/error states, thorough a11y, clean architecture seam, and 26 green tests. The house style is coherent and the comment voice is *why*-not-*what*. **The single thing standing between this and a Premium-gate PASS is the Pokémon/Nintendo IP in the fixtures (F1)** — a legal blocker that the gate question "would a top-tier studio ship this?" answers no to. Swap the IP for neutral invented cards (preserving the ~30× variant-price split) and re-audit; expect a pass. F2 (fabricated listing count) should ride along in the same refine cycle.

---
## Refine & gate resolution (orchestrator, 2026-06-18)
VETO finding F1 (Pokémon/Nintendo IP in shipped mock/demo data) resolved: all real card/set identities replaced with invented neutral cards (Emberwyrm Sovereign / Tidecaller Leviath / Grovekeeper Thornmaw across "Origins Vault"/"Echo Reprint"/"Wildgrowth"), mirrored in backend mock + mobile fixtures + all tests. The confirm-demo meaning is preserved: the two same-creature/different-set printings still split €757.10 vs €24.50 ≈ 30.9× (delta €732.60). Independent grep over apps/ confirms zero residual IP. F2 resolved: fabricated `listings={312}` removed from the value surface (no listing-count exists in the model). Suites green (backend 60, mobile 26). **Premium gate: PASS, veto cleared.**
