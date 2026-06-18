# @holofy/design-tokens

The single source of truth for Holofy's visual language — the **Foil Vault** system. Every surface, type ramp, motion curve, and the signature foil sweep lives here. Nothing in the app should hardcode a hex, a duration, or a radius; it consumes a token.

## The system in one breath

Holofy handles money and trust, so its default state is calm: deep near-black **Vault** surfaces, restrained type, generous space. Foil is the reward. The conic **foil sweep** and the magenta accent appear only at the moments that earn them — a card reveal, a rare pull, a milestone. Foil everywhere would cheapen it; foil held back makes it feel like treasure.

## What's here

| File | Role |
|------|------|
| `tokens.json` | **Edit this.** The authored source. Supports `{color.x.y}` aliases and a `comment` per token. |
| `tokens.ts` | Generated. Typed, nested `tokens` object — the editing-convenience source. |
| `tokens.css` | Generated. CSS custom properties under `:root`, plus a `[data-theme="light"]` block. |
| `dist/` | Generated. The package's runtime entry: `index.js` (ESM), `index.cjs` (CJS), `index.d.ts`. `main`/`exports` resolve here so consumers import real JS, never raw `.ts`. |
| `build.mjs` | Resolves aliases and emits all artifacts. `node build.mjs`. |
| `screens/` | Implementation-ready specs for the three signature screens. |

Regenerate after editing the JSON:

```bash
node build.mjs   # or: npm run build
```

## Consuming it

**Web / demos** — import the CSS once, then reference variables:

```css
@import "@holofy/design-tokens/css";

.value {
  font-family: var(--typography-scale-display-xl-family);
  font-size: var(--typography-scale-display-xl-size);
  letter-spacing: var(--typography-scale-display-xl-tracking);
  font-feature-settings: var(--typography-feature-tabular); /* prices never jitter */
  color: var(--color-semantic-dark-text-primary);
}
```

**React Native / TS** — import the typed object:

```ts
import { tokens } from "@holofy/design-tokens";

const styles = {
  surface: { backgroundColor: tokens.color.semantic.dark.bgElevated },
  reveal: { color: tokens.color.semantic.dark.reward },
};
```

## How the scales are built

- **Color** — three brand hues (`holoViolet`, `foilMagenta`, `vaultTeal`) each get a 50–900 tint ramp; a 0–1000 neutral ramp anchors on the `#0B0B12` Vault. **Semantic** tokens (`bg`, `textPrimary`, `accent`, `reward`, `lock`, …) are what UI consumes — never the raw ramps directly. Both `dark` (default) and `light` semantic sets exist; the CSS light block overrides the dark semantic vars so component code stays theme-agnostic.
- **Type** — Clash Display for headlines and the reveal value; Manrope for everything else. Manrope carries tabular figures: any price, grade, or counter sets `--typography-feature-tabular` so digit width never shifts mid-count-up.
- **Space** — a 2/4/8-based ramp (`space.1`…`space.13`). No magic margins.
- **Motion** — durations from `instant` (80ms) to `reveal` (900ms) and four easings. `spring` (slight overshoot) is reserved for the capture-lock snap and the value pop. Everything respects `prefers-reduced-motion` at the component level.

## The foil sweep

`--gradient-foil-sweep` is a conic gradient through the three brand hues, driven by `--foil-angle`. Bind that variable to device tilt (gyroscope), pointer position, or scroll to make the holo react. The companion `--gradient-foil-sheen` is the traveling specular highlight swept across a revealed card. See `screens/foil-reveal.md` for the choreography and `../../docs/design/demos/` for runnable proof.

## Rules that keep it non-generic

- Consume **semantic** tokens, not raw ramps, in product code.
- Foil/magenta are rewards — if a screen is at rest, it should read Vault-calm.
- Teal means *captured / verified / healthy*; amber means *seek review*; red is for **system** errors only — never an authenticity verdict.
- Tabular figures on every numeric that animates or compares.
