# Signature screen — Foil reveal (value reveal)

The payoff. The card is recognized, priced in euros, and presented back to the collector as a **revealed foil**: the captured card image lifts off the Vault, the conic foil sweep plays across it, and the value counts up in tabular figures. This is the single most brand-defining moment in the app — it has to feel like opening a pack, not reading a search result.

Restraint is what keeps it premium: the foil sweep plays **once** on reveal and then settles into a slow tilt-reactive shimmer. It is not a permanently spinning rainbow.

---

## Layout

Centered card hero, but the surrounding composition is deliberately *not* centered-everything:

1. **Card** — the user's captured card, rendered at `radius.card`, ~64% of viewport width, tilted into a subtle 3D resting pose (rotateX 6°, rotateY -8°). The foil overlay is masked to the card's holo regions where known; otherwise a full-card sheen.
2. **Value block** — left-aligned beneath the card. Eyebrow `overline` `MARKET VALUE · CARDMARKET`, then the count-up value in `displayXl`, then a `bodySm` `color.semantic.dark.textTertiary` line `30-day trend +4.2% · 312 listings`. A currency toggle `€ · $` sits inline-right of the value.
3. **Identity line** — above the card: `titleMd` card name, `caption` set · number · language · variant. If a variant is ambiguous, this is where the top-2 + price delta surfaces (master plan §5 — never silently guess).
4. **Actions** — bottom: primary `Add to collection`, secondary `Pre-grade this card` (the credit hook), tertiary text `Check authenticity`.

---

## Tokens used

- Background: `--gradient-vault-depth`.
- Card lift shadow: `elevation.foil`.
- Foil sweep: `--gradient-foil-sweep`, blend `screen`/`color-dodge` over the card, opacity ~0.55 at peak settling to ~0.18.
- Traveling highlight: `--gradient-foil-sheen` swept left→right once.
- Value: `displayXl`, family display, `font-feature-settings: var(--typography-feature-tabular)`, color `color.semantic.dark.textPrimary`. The currency symbol is `color.semantic.dark.reward` (magenta) — the one magenta touch.
- Eyebrow: `overline`, `color.semantic.dark.textTertiary`.
- Trend positive: `color.teal.400`; negative: `color.support.amber` (never red — a price dip is not an error).
- Primary action: `color.semantic.dark.accent` fill; secondary: accent 1.5px outline; tertiary: text only.

---

## Motion choreography

The reveal is a single ~900ms sequence, then it rests.

| t (ms) | Element | Motion |
|--------|---------|--------|
| 0 | Card | enters from 0.92 scale + 16px up, opacity 0→1 | `entrance` |
| 120 | Foil sweep | `--foil-angle` animates 210°→570° once across the card | `reveal` `entrance` |
| 180 | Sheen | `--gradient-foil-sheen` travels left→right across the card | `slow` `standard` |
| 200 | Value | count-up 0 → final, odometer roll on each digit | `countUp` `standard` |
| 240 | Identity + trend | fade/slide up 8px, staggered 40ms | `base` `entrance` |
| 900 | Settle | foil opacity eases 0.55→0.18; tilt-reactive shimmer takes over | `slow` `standard` |

**At rest** the card responds to device tilt (gyro) / pointer: `--foil-angle` tracks orientation within ±40°, so the holo lives gently. One brief specular pass every ~8s, easily missed — that's the point.

`prefers-reduced-motion`: no count-up (value appears final), no sweep animation — the foil renders as a static settled gradient at 0.18; no tilt tracking; card fades in without scale. The screen still reads premium, just still.

---

## States

- **Revealing** — the sequence above. Actions are present but disabled until settle (≈900ms) so nobody taps mid-animation.
- **Resting** — settled foil, tilt-reactive, actions live.
- **Loading / pricing** — card already shown, value block is a shimmer skeleton with eyebrow `FETCHING CARDMARKET PRICE`; the card foil plays its reveal regardless (the *recognition* succeeded). Honest: identity is known before price.
- **No price** — recognized but no liquid € comp: value block reads `No recent € sales` in `textSecondary`, with `caption` `We'll alert you when one lists` and a muted `$` fallback if available. Never shows a fabricated number.
- **Low-confidence variant** — identity line expands to a two-row chooser: each candidate with its own € value and the delta highlighted; `Confirm variant` required before Add. Trust over speed.
- **Error** — recognition failed entirely → not this screen; routes back to scan with `We couldn't read that one — try a cleaner shot or search by name`.

---

## Accessibility

- The value is announced once, settled, via a polite live region: `Market value, 42 euros 50, up 4.2 percent over 30 days`. The count-up animation is purely visual; SR users get the final figure immediately.
- Foil is decorative — `aria-hidden` on the sweep/sheen layers; the card image carries the real alt: `Your scanned card: Charizard, Base Set, number 4 of 102, English, holo`.
- Currency toggle is a real radio group with a label `Display currency`.
- Trend color is paired with a `+`/`−` glyph and the word `up`/`down` in the SR string — never color-only.
- All actions ≥44pt; primary is 52pt tall. Contrast AA on every text token over the Vault.
