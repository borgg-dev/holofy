import { tokens } from "./tokens";

// The app consumes a flat, RN-shaped `theme` rather than the raw token tree:
// it picks one semantic color set (dark or light) so component code never
// branches on scheme, and it exposes only the slices a screen actually styles
// with. Raw ramps (violet.400, teal.600…) stay reachable via `tokens` for the
// rare case a gradient stop needs them, but product styles use semantics.

export type ColorScheme = "dark" | "light";

// The dark and light semantic sets share keys but hold different literal hexes,
// so the runtime color object is keyed by the dark set's names with string values
// (a hex is a hex at runtime — components read names, never literal types).
type SemanticColors = Record<keyof (typeof tokens.color.semantic)["dark"], string>;

export type ThemeColors = SemanticColors & {
  // A few cross-scheme brand constants the Foil Vault leans on directly.
  vaultTeal: string;
  foilMagenta: string;
  holoViolet: string;
  amber: string;
  // Two further on-brand accents drawn from the ramps, so the Vault has a wider palette
  // of distinct game tints (a lighter violet, a deeper magenta) without an off-system hue.
  irisLavender: string;
  roseMagenta: string;
  amberSoft: string;
  onAmber: string;
  errorRed: string;
  vaultGlow: string;
};

function makeColors(scheme: ColorScheme): ThemeColors {
  const semantic = tokens.color.semantic[scheme];
  return {
    ...semantic,
    vaultTeal: tokens.color.brand.vaultTeal,
    foilMagenta: tokens.color.brand.foilMagenta,
    holoViolet: tokens.color.brand.holoViolet,
    amber: tokens.color.support.amber,
    irisLavender: tokens.color.violet["300"],
    roseMagenta: tokens.color.magenta["600"],
    amberSoft: tokens.color.support.amberSoft,
    onAmber: tokens.color.support.onAmber,
    errorRed: tokens.color.support.red,
    vaultGlow: tokens.color.vault.glow,
  };
}

export const space = tokens.space;
export const radius = tokens.radius;
export const elevation = tokens.elevation;
export const motion = tokens.motion;
export const gradient = tokens.gradient;

export function makeTheme(scheme: ColorScheme) {
  return {
    scheme,
    color: makeColors(scheme),
    space,
    radius,
    motion,
    gradient,
    /** Min interactive target for a11y; never tap-size below this. */
    tapTarget: tokens.size.tapTarget,
    cardRatio: tokens.size.card.ratio,
  } as const;
}

export type Theme = ReturnType<typeof makeTheme>;

export const darkTheme = makeTheme("dark");
export const lightTheme = makeTheme("light");
