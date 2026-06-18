# Audit — Design Foundation (Foil Vault)

**Auditor:** Design lens + Premium/Not-Generic gatekeeper (independent; did not build this).
**Date:** 2026-06-18
**Work unit:** Design Foundation — `packages/design-tokens/*`, `docs/design/FOUNDATION.md`, `docs/design/demos/*`.
**Rubrics applied:** Charter §3.4 (Frontend/Design), §3.6 (Premium/Not-Generic — VETO).

## Verdict

- **§3.4 Frontend/Design:** PASS — every criterion ≥2, lens average **2.75**.
- **§3.6 Premium gate:** **PASS (no veto)** — every criterion ≥2, **zero AI-tells** found.
- Caveat: this is a *foundation* (tokens + specs + browser demos), not shipped RN product. The bar is met for what it claims to be. Several criteria are scored on *specified* behavior (states, motion, a11y) that must be re-audited when implemented in React Native.

I went in looking for a reason to veto. I didn't find one. This is the rare case where the not-generic claim is backed by actual bespoke geometry and restraint, not asserted in a README.

---

## §3.4 Frontend / Design

| Criterion | Score | Notes |
|---|---|---|
| Bespoke, zero default-framework chrome | 3 | No framework, no component library, no Bootstrap/Tailwind/MUI fingerprints. Buttons, chips, gauge, capture frame, foil card are all hand-built from the token vocabulary. |
| Custom components / matches Foil Vault | 3 | Conic foil sweep, traveling specular sheen, corner-bracket capture frame, luminous grade *band* (not a needle), provenance tags — all specific to this product's domain. |
| Intentional motion + `prefers-reduced-motion` | 3 | Choreography is per-screen, timed, and purposeful (lock-snap spring, reveal sweep once-then-settle, staggered meter fills). Reduced-motion handled in **both** CSS and JS (count-up, sweep, tilt all gated on `matchMedia`). `@property --foil-angle` is correctly declared so the conic angle can actually interpolate — a non-obvious craft detail. |
| States + alignment + a11y (contrast/SR/44pt/locale) | 2 | Specs enumerate real loading/empty/error/refused/out-of-credits/low-confidence-variant states. Contrast claims independently verified (see below). 44pt targets present; SR strings specified; `€1.234,56`/`42,50` locale formatting demonstrated. Held at 2 (not 3) because the demos render the *happy/locked* path only — the specified non-happy states are documented, not yet provable in the demos, and a few are RN-only. |

**Lens average: 2.75 → PASS.**

### Contrast verification (recomputed, WCAG 2.1)
FOUNDATION.md's numbers are accurate, not decorative:

| Pair | Claimed | Recomputed |
|---|---|---|
| primary white on Vault | 19.6:1 | 19.61 |
| secondary `#C4C4D4` on Vault | 11.4:1 | 11.39 |
| teal on Vault | 10.7:1 | 10.66 |
| amber on Vault | 10.7:1 | 10.72 |
| white-on-violet button | 6.3:1 | 6.25 |
| `textTertiary #74748C` on Vault | 4.3:1 | 4.31 |

The honest handling of `textTertiary` (4.31:1 — below 4.5 body AA, explicitly restricted to large/caption where the 3:1 bar applies) is exactly the kind of disclosed limitation a studio documents rather than papers over.

### Legal / honest-framing posture (§3.1, master plan §6) — clean
- No "Pokémon"/"Poké"/"-dex", no character art, Poké Balls, type symbols, or official typeface anywhere. Demo card art is built from gradients.
- Grade output is a **range** (`Likely 8–9`) + sub-scores + confidence + a permanent, non-dismissible disclaimer naming PSA/CGC/Nintendo/TPC. No single-number grade.
- Authenticity is never a binary "FAKE": `red` is reserved for system errors in the token comments and the gauge/verdict copy uses amber "seek review".
- Trend-down is amber, not red ("a price dip is information, not an error"). This discipline is encoded in the tokens, the screen specs, AND the demos consistently.

---

## §3.6 Premium / Not-Generic gate (VETO)

| AI-tell checked | Present? | Evidence |
|---|---|---|
| Generic/stock look; default component-library styling | No | Bespoke throughout; no library chrome. |
| Centered-everything layout | No | Reveal value block and identity line are deliberately left-aligned; only the card hero centers (a hero should). Stated intent matches the CSS. |
| Lorem/placeholder/TODO copy | No | Every string is real product microcopy in a consistent voice ("Let's get a cleaner shot — tilt away from the light", "A pre-screen, not a grade", "Fast mode — value only, no grade"). |
| Over-commenting (what-not-why) | No | Comments explain *why* ("the one magenta touch", "Honest: identity is known before price", "not a fake-progress bar"). Build script comments are purposeful. |
| Speculative abstraction / dead code / `foo`/`temp`/`handleData` | No | Naming is domain-precise (`foilSweep`, `lockGlow`, `vaultDepth`, `setLocked`, `refuse`, `countUp`). One harmless dead line in the gauge JS (`const c = track.getPointAtLength(len/2)` is computed then unused) — see findings, not a tell. |
| Boilerplate/marketing README voice; em-dash hype soup; emoji-as-decoration | No | README and FOUNDATION read like a design lead wrote them, with restraint. No emoji in product UI; icons are drawn SVG. Em-dashes are used for prose, not hype-stacking. |
| Inconsistent house style across files | No | One token vocabulary, one spacing ramp, one motion language, one button system shared across all three demos via `demo.css`. |
| Missing unglamorous polish (focus/transition/error microcopy/edge cases) | No | `:focus-visible` rings on every control, transitions tokenized, error/refused microcopy written, edge cases (no-price, low-confidence variant, out-of-credits, surface-blind, permission-denied) all specified. |

**Positive bar (coherent house style, domain-precise naming, restraint, taste, unglamorous details):** met. Restraint is the thesis and it's actually executed — foil/magenta are rationed to three reward moments; everything else is Vault-calm. That is the difference between premium and a gradient someone left on.

**Premium gate: PASS. No veto.**

---

## Findings (prioritized)

Nothing here blocks the gate. P2/P3 are "what would make it studio-grade-er" and packaging hygiene to resolve before RN consumption.

### P1 — fix before this is consumed as a package
1. **`main` points to a `.ts` file.** `package.json` sets `"main": "./tokens.ts"` and `exports["."]` to the same. Plain Node and most bundlers can't `import` raw TS without a transpile step, yet README shows `import { tokens } from "@holofy/design-tokens"`. Either ship a compiled `.js`/`.d.ts` pair or document that consumers must have TS resolution. Today the documented import path is not actually runnable as-is.

### P2 — would raise §3.4 to a clean 3 across the board
2. **Demos prove only the happy path.** The specs describe excellent empty/error/refused/out-of-credits/surface-blind/low-confidence-variant states, but the runnable demos render the locked/revealed/result state only. Add a state toggle (or a second view) per demo so the unglamorous states are *provable*, not just promised. This is the single biggest gap between "documented well" and "demonstrated."
3. **`@property --foil-angle` is declared only in `foil-reveal.html`.** The token `--gradient-foil-sweep` is used in `index.html` (brand mark, swatch) and `scan-frame` context with static angles, so they're fine — but any future animation of `--foil-angle` outside the reveal demo will jump instead of interpolate. Promote the `@property` declaration into `tokens.css` (or a shared base) so the foil sweep animates correctly everywhere by default. Note this won't carry to React Native/Skia, where the holo is a shader — fine, but call it out so nobody assumes the CSS technique transfers.

### P3 — polish / hygiene
4. **Dead line in `pre-grade-gauge.html`.** `const c = track.getPointAtLength(len / 2)` is computed and never used (the adjacent comment even admits "center reference not needed"). Delete it — leaving acknowledged-dead code in a file whose job is to demonstrate craft is a small self-inflicted ding against §3.6.
5. **Chip/shutter text color sourced from raw ramp.** `scan-frame.html` uses `--color-neutral-900` directly for chip and shutter text rather than a semantic token. The README's own rule is "consume semantic tokens, not raw ramps, in product code." Demos get a pass, but if any of this CSS is lifted into product it violates the house rule. Consider a `text-on-glass`/`text-on-camera` semantic token for the camera-overlay context.
6. **Focus ring has no offset.** `box-shadow: 0 0 0 3px focus-ring` sits flush against the control. On the Vault it reads fine; in the light theme it can blend into adjacent fills. Add a 1–2px offset (inner transparent ring) for theme-robust focus visibility.
7. **`gradient.vaultDepth`/`lockGlow` JSON formatting.** The closing `}` for `vaultDepth` is on its own line with the next key's comma leading — valid JSON, parses fine (build emits 144 tokens cleanly), but it's a stylistic wobble in an otherwise immaculate source file. Cosmetic.

---

## Build check
`node build.mjs` runs clean: "Wrote tokens.ts and tokens.css from 144 tokens." Regenerated output is byte-identical to the committed artifacts (no drift). Alias resolution (`{color.brand.holoViolet}` etc.) and typography-composite expansion both correct; no unresolved `{...}` references remain in the generated CSS; light theme correctly overrides the `--color-semantic-dark-*` vars so component code stays theme-agnostic.

## Bottom line
Studio-grade foundation. The not-generic claim is earned, not asserted. Clear the P1 packaging issue and add state-coverage to the demos (P2) and there's nothing left to argue with. **PASS / no veto.**
