# Holofy — mobile

The React Native (Expo) app. This slice (P1.3) is the foundation: the design-token
theme layer, the bespoke Foil Vault primitives, and the scan-frame screen shell.
It is **not** the full scan flow (recognition → € value → portfolio) — that's P1.4.

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
  _layout.tsx            fonts + Vault paint + theme/safe-area providers
  index.tsx              → ScanScreen (the app's front door)
src/
  theme/                 tokens → RN theme (dark default + light), type, motion
  components/            bespoke primitives — Screen, FoilSurface, Text,
                         ValueText, QualityChip, Shutter, ModeToggle, ScanFrame…
  screens/scan/          the scan-frame screen, its copy, and mock capture state
```

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
- `tsc --strict --noUncheckedIndexedAccess` passes on the token-consuming theme
  layer (`theme/theme.ts`, `theme/color.ts`) against the **real** generated `.d.ts`,
  and on the scan logic (`screens/scan/copy.ts`, `useMockCaptureQuality.ts`).
  The strict pass caught and fixed two real issues (a too-narrow color type and an
  unchecked index access).
- No hardcoded design colors in `src/` — the only hex literals are clearly-named
  **mock camera-photo** tones in `CameraPreview.tsx`, deleted with the real feed.

**Needs a device / simulator (not runnable here):**
- A full `npm install` of the native toolchain (Expo/RN/reanimated/camera).
- `tsc --noEmit` across the `.tsx` tree (needs the Expo/RN type packages installed).
- The lock haptic, the reanimated lock-snap/breathe/shake choreography, font load,
  and the live `prefers-reduced-motion` behavior — all need a real runtime.

## The scan-frame screen (P1.3 deliverable)

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
signal stream lands in P1.4; the lock / refuse / announce wiring around it is real.
