# Fonts

Holofy's type system uses two OFL (free, redistributable) families. They are
**not committed** (kept out of git per `.gitignore`); fetch them once into this
folder before running on a device. File names must match exactly — `theme/fonts.ts`
references them by name and a mismatch fails loudly at load.

| File | Family · weight | Source |
|------|-----------------|--------|
| `ClashDisplay-Semibold.otf` | Clash Display 600 | fontshare.com/fonts/clash-display |
| `Manrope-Regular.ttf` | Manrope 400 | fonts.google.com/specimen/Manrope |
| `Manrope-Medium.ttf` | Manrope 500 | fonts.google.com/specimen/Manrope |
| `Manrope-SemiBold.ttf` | Manrope 600 | fonts.google.com/specimen/Manrope |
| `Manrope-Bold.ttf` | Manrope 700 | fonts.google.com/specimen/Manrope |

Clash Display carries the display weight (600) used for headlines and the reveal
value; Manrope carries the UI ramp and the tabular figures prices depend on.
