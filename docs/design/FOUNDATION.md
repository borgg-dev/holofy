# Holofy design foundation — Foil Vault

This is the visual bedrock everything else is built on: a single token source, three implementation-ready signature screens, and runnable proof you can open in a browser. It exists to make one promise enforceable — *Holofy looks like a top-tier studio built it, never like generic output* (charter §3.6).

## The idea

Holofy helps people decide whether to spend real money — to buy a card, or to send one to PSA. That responsibility sets the tone: the resting state is **Vault** — deep near-black surfaces, restrained type, generous space, calm. Trust is the default.

Then there's the **foil**. The holographic shimmer is the one thing that's unmistakably ours, and it's legally clean (a printing technique, not Pokémon IP). We treat it as a reward, not a texture. It appears at the three moments that earn it — locking a clean scan, revealing a card's value, weighing a grade — and nowhere else. Scarcity is what keeps it feeling like treasure instead of a gradient someone left on.

## What's in the foundation

| Piece | Path | What it is |
|-------|------|-----------|
| Token source | `packages/design-tokens/tokens.json` | The authored single source of truth. Aliases, comments, dark + light. |
| TS tokens | `packages/design-tokens/tokens.ts` | Generated typed object for RN/TS. |
| CSS tokens | `packages/design-tokens/tokens.css` | Generated custom properties + light theme. |
| Build | `packages/design-tokens/build.mjs` | Resolves aliases, emits both artifacts, mirrors CSS to the demos. |
| Screen specs | `packages/design-tokens/screens/*.md` | Layout, tokens, motion, states, a11y for each signature screen. |
| Runnable demos | `docs/design/demos/*.html` | Self-contained, open in a browser, the look is real. |

Open `docs/design/demos/index.html` to see all three.

## The three signature screens

1. **Scan frame** (`scan-frame.html`) — the capture-lock. A searching dashed frame snaps to a solid teal bracket with a soft aura the instant focus/glare/corners cross threshold; a haptic fires; the card *clicks into place*. Quality chips coach honestly and never show red — a not-yet-good photo is a coaching state, not a failure. The app refuses to grade sub-threshold photos (master plan §7).
2. **Foil reveal** (`foil-reveal.html`) — the payoff. The card lifts off the Vault, the conic foil sweep plays **once**, a specular sheen travels across it, and the value counts up in tabular euros. Then it settles into a slow tilt-reactive shimmer. Pointer-move stands in for the gyroscope.
3. **Pre-grade gauge** (`pre-grade-gauge.html`) — the trust screen. An honest grade *range* painted as a luminous band (not a needle), four sub-scores with their provenance shown (`measured` vs `estimated`), a surface caveat when the raking-light pass was incomplete, and a permanent, non-dismissible disclaimer. No foil here — celebration would undercut the gravity of a grading decision.

## How this clears the Premium gate (§3.6)

The gate auto-fails on a list of AI-tells. Point by point:

- **Not generic / no stock look** — bespoke conic foil sweep, custom gauge geometry, corner-bracket capture frame, a house button system. Zero default-component-library chrome.
- **Not centered-everything** — the reveal value block and identity line are deliberately left-aligned; only the card hero centers, because a hero should.
- **No placeholder copy** — every string is real product microcopy in the brand's voice ("Let's get a cleaner shot — tilt away from the light", "A pre-screen, not a grade"). No lorem, no `TODO`.
- **No emoji-as-decoration, no em-dash hype** — icons are drawn SVG; copy is plain and declarative.
- **Coherent house style** — one token vocabulary, one spacing ramp, one motion language across all three screens and both packages.
- **The unglamorous polish** — focus-visible rings on every control, 44pt targets, real loading/empty/error/refused/out-of-credits states specified per screen, `prefers-reduced-motion` honored in CSS *and* JS, tabular figures so digits never jitter mid-count.
- **Restraint** — foil and magenta are rationed to the reward moments; the rest is Vault-calm. That restraint is the point.

## Honest framing & legal (charter §3.1, master plan §6)

- Pre-grade is always a **range + sub-scores + confidence + disclaimer**, never a single number. Surface uncertainty widens the range visibly rather than hiding it.
- Authenticity is never a binary public "FAKE"; the palette reserves red for **system** errors only, amber for "seek review".
- Trend down is amber, not red — a price dip is information, not an error.
- No Pokémon/Nintendo IP in our branding: no Poké Balls, character art, type symbols, or the official typeface. The demo card art is built from gradients. The disclaimer naming PSA/CGC/Nintendo/TPC ships on the grade screen.

## Accessibility notes (verified)

Contrast over the Vault (`#0B0B12`): primary text 19.6:1, secondary 11.4:1, teal 10.7:1, amber 10.7:1, white-on-violet button 6.3:1 — all comfortably AA+. `textTertiary` (`#74748C`) is 4.3:1 and is therefore restricted to large/caption sizes (where the 3:1 large-text bar applies) — never body. Color is never the sole signal: every state pairs a color with a word or glyph, and screen-reader strings are specified per screen.

## Consuming & extending

Edit `tokens.json`, run `node packages/design-tokens/build.mjs`, and the TS, CSS, and demo copies regenerate. Product code consumes **semantic** tokens (`color.semantic.dark.*`), never raw ramps, so theming stays a one-line switch. See `packages/design-tokens/README.md` for the full consumption guide.
