# Audit — P1.3 RN scan-frame app + design-tokens dist build

**Auditor:** independent design/premium/architecture lens (not the builder)
**Date:** 2026-06-18
**Artifacts:** `apps/mobile/` (RN/Expo scan-frame screen) · `packages/design-tokens/` (dist build change, carry-over from P1)
**Charter applied:** §3.4 Frontend/Design · §3.6 Premium gate (VETO) · §3.2 Architecture
**Spec:** `packages/design-tokens/screens/scan-frame.md` · Master plan §6, §7

---

## Verdict

**PREMIUM GATE: PASS (no veto).** Every §3.6 criterion ≥2, **zero AI-tells** found. This is genuinely bespoke "Foil Vault" work, not competent-but-generic RN. The signature lock choreography, the coaching-not-error chip system, the refuse-to-grade shutter, and the token discipline all read as a studio house style with intent behind each decision.

**§3.4 Frontend/Design: PASS** (avg 2.75, every criterion ≥2).
**§3.2 Architecture: PASS** (avg 2.75).
**§3.6 Premium: PASS** (every criterion ≥2, zero AI-tells).

It is *better than good*. The findings below are what separates it from flawless — none are gate-blocking, but #1 and #2 should be cleaned before this file is held up as the house reference.

**Verification caveat:** dependencies are not installed (`apps/mobile/node_modules` absent), so `tsc --noEmit` and `eslint` could not be executed, and nothing runs on a device. The builder was explicit that device behavior (haptics, reanimated, font load, live reduce-motion) is unverifiable here. I verified everything statically verifiable: the token build, package exports, hex-literal hunt, spec conformance by reading, and house-style consistency.

---

## §3.4 Frontend / Design

| Criterion | Score | Notes |
|---|---|---|
| Bespoke, zero default-framework chrome | **3** | No default RN chrome anywhere. Headers off (`_layout.tsx`), nav bar painted Vault before first paint, every control is custom: corner-bracket frame, pill shutter, segmented Scan/Stack, blurred-disc icon buttons, hand-drawn SVG icons. No stock-library look. |
| Custom components, matches Foil Vault | **3** | `FoilSurface` (scarce violet foil-edge), `VaultGround` radial depth (explicitly "never flat black"), `ScanFrame`, `Shutter`, `QualityChip`, `CoachingToast` are domain primitives. House style is coherent across files. |
| Intentional motion + reduced-motion | **3** | Lock snap (1.04→1.0 spring), searching breathe (1.0→1.015 loop), dot color crossfade, shutter fill + ±4px shake-twice refusal, toast slide. `prefers-reduced-motion` handled per-component and matches the spec table exactly: drops breathe + scale-snap + shake, **keeps** color/glow for state legibility (`ScanFrame.tsx:42,57`, `Shutter.tsx:42`, `QualityChip.tsx:37`). |
| Real states + a11y + alignment | **2** | a11y is strong (see below). Optical placement is intentional (frame ~46%, chips don't crowd). **Gap:** of the spec's 7 states, only Searching / Locked / Refused / Stack are implemented; **Multi-angle guided, No-card/empty, Permission-denied are not** (empty-state copy `EMPTY_HINT` is authored in `copy.ts:49` but never rendered). Acceptable for a P1.3 mock slice, but it's why this criterion is 2 not 3. |

**Lens avg: 2.75 → PASS.**

Accessibility highlights (genuinely the unglamorous polish done right):
- Each chip carries `accessibilityLabel="${signal}: ${label}"` and the label text changes with state — color is never the sole signal (`QualityChip.tsx:49`), exactly per spec §Accessibility.
- Lock fires `announceForAccessibility(LOCK_ANNOUNCE)` (`ScanScreen.tsx:57`); toast is `role="alert"` + `liveRegion="polite"` (`CoachingToast.tsx:42`).
- Shutter disabled state: `accessibilityState={{ disabled: !locked }}` + a hint describing what's missing (`Shutter.tsx:66`).
- 44pt targets via `theme.tapTarget`; shutter `minHeight: 56`. Matches spec.
- `ValueText` Intl-formats `€1.234,56` for `de-DE` with a Hermes-missing-Intl fallback (`ValueText.tsx:42`) — locale/currency formatting per §3.4.

---

## §3.2 Architecture

| Criterion | Score | Notes |
|---|---|---|
| Fits system design, ML stages swappable | **3** | `useMockCaptureQuality` is explicitly a stand-in whose **shape is the real contract** (`{signal→state}` snapshot + derived `locked`/`firstFailing`); documented as "replaced wholesale in P1.4." `CameraPreview` is a labeled placeholder for `expo-camera`. The capture↔ML handshake (master plan §7) is honored: the screen *refuses to grade* sub-threshold shots and loops to coaching. |
| Clean module boundaries, no leaky coupling | **3** | Strict layering: `tokens.json` → `dist` → app `theme/tokens.ts` re-export → `theme.ts` flat RN theme → components. App code reads semantic names, never literal hexes or the raw token package. `copy.ts` isolates all microcopy as the l10n seam. No premature abstraction. |
| Data-capture/consent loop | **n/a** | No user content captured in this slice (mock). Correctly out of scope. |
| Decisions traceable | **2** | Rationale is captured inline as *why*-comments (e.g. why a `dist/`, why per-side bracket borders, why fontWeight is still set). No ADR was filed for the dist/exports decision, which is a reasonable candidate given it was a carry-over P1 fix. Minor. |

**Lens avg: 2.75 → PASS.**

**design-tokens dist build (carry-over P1 fix) — verified:**
- `node build.mjs` runs clean, emits `dist/index.js` (ESM), `dist/index.cjs` (CJS), `dist/index.d.ts` from 146 tokens. The `.d.ts` preserves literal types (each hex is its own string-literal), so downstream autocomplete is exact.
- `package.json` `main`/`module`/`types`/`exports` all point at `dist/`, **not** raw `.ts` — the P1 carry-over is resolved (`packages/design-tokens/package.json:7-19`). App imports resolve to compiled JS; Metro/tsc never see raw TS.

---

## §3.6 Premium / Not-Generic gate — AI-tell sweep

Hunted the full auto-FAIL list. Result per tell:

- **Generic/stock look, default styling, centered-everything** — NOT present. Layout is deliberately asymmetric (top bar back/toggle/flash, frame above optical center, bottom coaching strip). The shutter is explicitly *not* a generic round button.
- **Lorem/placeholder copy** — NOT present. All microcopy is real, domain-precise, and on-brand ("Hold steady" → "Capture", "Glare on holo", "Show full card", "Let's get a cleaner shot — tilt away from the light."). Copy never blames the user, matching the spec's coaching posture.
- **Emoji-as-decoration** — NOT present. Icons are hand-drawn stroke SVGs; the icon file even comments that it deliberately avoids emoji glyphs.
- **Over-commenting that narrates *what*** — NOT present. Comments explain *why* (why dashed flips discretely, why fontWeight stays set, why a dist exists). This is the good kind.
- **Hardcoded design colors** — effectively NOT present. Hex hunt over `src/` returns exactly: `MOCK_TABLE_DARK`/`MOCK_TABLE_LIT` (named mock *photo content*, documented to be deleted with `CameraPreview`) and `shadowColor: "#000"` (a standard RN shadow, not a design color). Both legitimate. Builder's claim verified.
- **Dead code / speculative abstraction / `foo`/`temp` naming** — naming is domain-precise throughout (`firstFailing`, `refuseSignal`, `lockGlow`). See finding #3 for two exported-but-unused components.
- **Missing focus/transition/error microcopy / edge cases** — refusal microcopy, disabled hints, live-region announcements, and Intl fallback are all present.
- **Inconsistent house style** — one real instance, finding #1 below.

**Zero gate-blocking AI-tells → PASS, no veto.**

---

## Prioritized findings (none gate-blocking)

**1. House-style inconsistency: raw layout literals in `ScanScreen` styles.** (`apps/mobile/src/screens/scan/ScanScreen.tsx:190-200`)
The `coach` / `chips` StyleSheet uses raw numbers — `paddingHorizontal: 16`, `paddingBottom: 40`, `paddingTop: 24`, `gap: 20`, `gap: 8` — every one of which maps exactly to a token (`space.5`, `space.9`, `space.7`, `space.6`, `space.3`). The *same file's* `TopBar` correctly uses `theme.space["5"]/["7"]`. That's mixed convention inside one file, the precise §3.6 "inconsistent house style" tell. It doesn't trip the gate because the values are correct and the file is otherwise disciplined, but it should be tokenized for the file to serve as the reference. The `vignette` `64`s are arguably intentional non-token magic, but should still be named constants.

**2. README overclaims.** (`apps/mobile/README.md:31`) States "Nothing hardcodes a hex, radius, duration, or font size — everything resolves from `@holofy/design-tokens`." Finding #1 plus `Shutter.tsx:86` (`borderWidth: 1.5`, `minHeight: 56`), `QualityChip.tsx:76` (`8/8/4`), and `ScanFrame.tsx:23` (`BRACKET = 32`) contradict the absolute claim. Spacing/radii leak in several spots. Soften the README to "design colors and the type scale resolve from tokens; a few component-intrinsic dimensions are local constants," or finish tokenizing. Marketing-grade absolute claims that the code doesn't honor are themselves a soft premium-tell.

**3. Exported-but-unused components for this slice.** `FoilSurface` and `ValueText` are fully built and exported from `components/index.ts` but referenced nowhere in the P1.3 screen. They're clearly forward-built house primitives (the value primitive is the wedge's number), not dead code, and both are high quality — but per §3.6 they read as unused until a screen consumes them. Fine to keep as the component library seeds; flag so a later audit doesn't re-litigate them.

**4. Ship-time cleanup already flagged by the builder.** The on-screen "Demo: tap to advance capture quality" affordance (`ScanScreen.tsx:120-128`) is a dev control in product UI. The builder annotated it "trimmed in P1.4." Acceptable for a mock slice; must not survive into a shippable build (it would be a clear premium-tell in production).

**5. Stale committed token source (minor).** Running `node build.mjs` produced a 2-line `tokens.css` and 4-line `tokens.ts` diff (added `onAmber`, `vault.glow`), i.e. the committed generated files were slightly behind `tokens.json`. `dist/` was already current. Re-run the build and commit so generated artifacts match source; consider a CI check that fails on a dirty tree after build.

**6. `fontError` fallback is silent.** (`apps/mobile/app/_layout.tsx`) On `fontError` the app proceeds without brand fonts and nothing surfaces it. Reasonable to not block first paint, but a dev-time warning would help catch a broken OFL fetch (fonts are not committed — `assets/fonts/` holds only a README).

---

## What would make it studio-grade (3/3 across the board)

- Implement the three missing spec states — **Multi-angle guided** (`2 / 3 · Tilt left 15°` + tilt indicator, required for pre-grade/anti-fake per §7.3), **No-card/empty** (wire the already-authored `EMPTY_HINT` after >6s of no detection), and **Permission-denied** (the one red-adjacent full-screen Vault state). These are the difference between "demonstrates the lock" and "ships the screen."
- Tokenize the remaining raw spacing in `ScanScreen` styles (finding #1) so every screen is a clean reference.
- File a short ADR for the tokens `dist/`+`exports` decision (it's the kind of non-obvious infra choice §3.2 wants traceable).

---

## Bottom line

A demanding read finds this **genuinely premium and bespoke** — the coaching-not-error chip semantics, the felt lock + refusal, the a11y label-changes-with-color discipline, and the strict token→theme→component layering are exactly the "unglamorous details done right" the charter demands. **Premium gate PASS, no veto.** §3.4 and §3.2 pass. Refine items are polish (tokenize stray literals, soften the README, schedule the missing states for the slice that adds the real camera), not failures.
