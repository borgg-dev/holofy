# Holofy — mobile

The React Native (Expo) app. The design-token theme layer, the bespoke Foil Vault
primitives, the typed API client, and the **full core scan flow** (P1.3 + P1.4):
scan-frame → capture → recognize → **foil reveal** (or **low-confidence confirm**) →
Add to Vault → the **Vault** (portfolio) reflects it.

## Stack

- **Expo SDK 51** · React Native 0.74 · TypeScript (strict)
- **expo-router** — file-based routing (`app/`), headerless; screens own their chrome
- **react-native-reanimated 3** — the lock snap, chip crossfade, refuse shake
- **expo-camera** — declared for P1.4; the feed is a placeholder here
- **expo-haptics** — the single medium impact on capture-lock
- **@holofy/design-tokens** — the only source of color/space/type/motion

## Layout

```
app/                     expo-router routes
  _layout.tsx            fonts + Vault paint + theme/api/flow/safe-area providers
  index.tsx              → ScanScreen (the app's front door); capture → scan → route
  reveal.tsx             → RevealScreen (the foil reveal payoff)
  confirm.tsx            → ConfirmScreen (low-confidence top-2 + € delta)
  vault.tsx              → VaultScreen (the portfolio)
src/
  theme/                 tokens → RN theme (dark default + light), type, motion
  api/                   typed client (fixture + HTTP), models, mapping, fixtures
  flow/                  ScanFlowProvider — carries the in-flight scan + Add action
  components/            bespoke primitives — Screen, FoilSurface, FoilCard, Text,
                         ValueText, CountUpValue, Button, Skeleton, QualityChip,
                         Shutter, ModeToggle, ScanFrame…
  screens/scan/          the scan-frame screen, its copy, and mock capture state
  screens/reveal/        the foil value reveal + its copy
  screens/confirm/       the variant disambiguation chooser
  screens/vault/         the portfolio screen
  screens/shared/        cross-screen formatting (identity/trend) + TrendPill
```

## The flow

`ApiProvider` defaults to the **fixture client**, so the whole flow runs with no
backend (point at staging with a `mode="http"` change in `app/_layout.tsx`).
`ScanFlowProvider` holds the in-flight scan result and the Add-to-Vault action so the
route screens stay thin and a `CardIdentity` never serializes through URL params.

- **Reveal** (`screens/reveal/foil-reveal.md`): the card lifts off the Vault with a
  once-only foil sweep (`FoilCard`), the € value counts up in tabular figures, the
  identity + 30-day trend settle in, and actions stay disabled until the reveal
  settles (~900ms). States: revealing, resting, **pricing** (value skeleton),
  **no-price** (never a fabricated number). Reduced motion → instant settled value.
- **Confirm** (low-confidence): renders `/scan` `needs_confirmation` as the top-2
  candidates with each price and the **€ delta** called out — the reason to ask.
  A real radiogroup; Confirm required before Add (trust over speed).
- **Vault**: total € value (count-up, foil glow), change vs last snapshot, card count,
  and the holdings list with each card's current € contribution. Loading / empty /
  error are all real states; refetches when the flow signals a new Add.

## Design-token contract

Nothing hardcodes a hex, radius, duration, or font size — everything resolves from
`@holofy/design-tokens`. The package compiles to `dist/` (ESM + CJS + `.d.ts`), so
Metro and `tsc` import real JS, never raw `.ts`. Regenerate after editing tokens:

```bash
npm run tokens     # = node ../../packages/design-tokens/build.mjs
```

`src/theme` picks one semantic color set per scheme so component code reads color
*names* (`color.lock`, `color.reward`), never literals. Dark is the default; an
explicit OS "light" flips the set. `prefers-reduced-motion` is read once at the
provider and threaded to every signature animation.

## Run it on a real machine

This is a native app; it needs the full toolchain and a device/simulator — none of
which runs in CI here. On a dev machine:

```bash
# from the repo root — workspaces link @holofy/design-tokens automatically
npm install
npm run tokens                    # build the token dist once

cd apps/mobile
# fonts are OFL and not committed — fetch them first (see assets/fonts/README.md)
npx expo start                    # then press i / a, or scan the QR in Expo Go
```

`expo-camera` and reanimated need a dev client or a real build, not web preview, for
the scan screen to run with native modules.

## What was verified here vs what needs a device

**Verified in this environment (no native run):**
- `packages/design-tokens` builds clean — `node build.mjs` emits `tokens.ts`,
  `tokens.css`, and `dist/{index.js,index.cjs,index.d.ts}` from 146 tokens.
- The compiled package resolves and imports both as **ESM and CJS** through its
  `exports` map (`tokens.color.semantic.dark.lock` etc. read correctly at runtime).
- `npm test` is green — **26 tests** via `node --test` (strip-types), covering the
  API client/mapping/fixtures, the full fixture flow (scan → add → portfolio total
  reflects it), the count-up easing, and the new cross-screen formatters
  (`screens/shared/format.ts`: identity sub-line, SR labels, trend derivation/sign,
  EU percent formatting — a price dip reads as "down", never an error).
- `tsc --strict --noUncheckedIndexedAccess` is clean on `screens/shared/format.ts`
  against the real model types.
- No hardcoded design colors in any flow file — `grep` over `screens/{reveal,confirm,
  vault,shared}`, `flow/`, and the new components finds **zero** hex literals; all
  color/spacing/radius/motion resolves from `@holofy/design-tokens`.

**Needs a device / simulator (not runnable here):**
- A full `npm install` of the native toolchain (Expo/RN/reanimated/camera) — so
  `tsc --noEmit` across the full `.tsx` tree and `eslint` aren't runnable here.
- The reveal foil-sweep/sheen/count-up choreography, the lock haptic, font load, and
  the live `prefers-reduced-motion` behavior all need a real runtime. The reduced-
  motion branches (instant value, no sweep, static skeleton) are wired but unverified
  on-device.

## The scan-frame screen

Implements `packages/design-tokens/screens/scan-frame.md`:

- **Corner-bracket target**, not a full rectangle — searching it breathes with a
  dashed neutral stroke; on lock it snaps to a solid teal stroke with a teal aura.
- **Three quality chips** (focus / glare / framing) driven by mock capture state.
  Amber = a coaching state, never red; the label text changes with the color so
  state is never conveyed by color alone.
- **Shutter** is a teal-outlined pill (`Hold steady`), filling teal (`Capture`) on
  lock. An early tap doesn't fail silently — it shakes and surfaces the specific
  coaching line ("Let's get a cleaner shot — tilt away from the light").
- **Lock** fires one medium haptic and a polite screen-reader announcement.
- **Reduced motion** drops the breathe loop, the lock scale snap, and the shake;
  it keeps the color/glow crossfade so state stays legible.

Capture quality is mock-driven (`useMockCaptureQuality`) — the real on-device
signal stream replaces it later; the lock / refuse / announce wiring around it is
real. A locked capture runs recognition and routes by outcome (reveal vs confirm);
the demo build alternates a high-confidence and a low-confidence bundle so both
paths are reachable without a camera.
