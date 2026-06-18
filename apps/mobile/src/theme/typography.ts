import type { TextStyle } from "react-native";

import { tokens } from "./tokens";

// Maps the token type scale to RN TextStyle. Two things the web tokens express
// that RN needs translated:
//   - `family` is a token alias ("display" | "text"); RN wants a concrete
//     fontFamily string that matches what expo-font loaded.
//   - tabular figures: web uses font-feature-settings; RN uses fontVariant.
//     Anything that animates or compares numerically opts in via `tabular`.

// Font family names as registered with expo-font in App bootstrap.
// We map by weight because RN on Android can't synthesize weights from one file.
export const fontFamily = {
  // Clash Display ships the display weight we use (600).
  displaySemibold: "ClashDisplay-Semibold",
  text: "Manrope-Regular",
  textMedium: "Manrope-Medium",
  textSemibold: "Manrope-SemiBold",
  textBold: "Manrope-Bold",
} as const;

type ScaleKey = keyof typeof tokens.typography.scale;

function familyFor(family: string, weight: number): string {
  if (family === "display") return fontFamily.displaySemibold;
  if (weight >= 700) return fontFamily.textBold;
  if (weight >= 600) return fontFamily.textSemibold;
  if (weight >= 500) return fontFamily.textMedium;
  return fontFamily.text;
}

function build(key: ScaleKey): TextStyle {
  const s = tokens.typography.scale[key];
  return {
    fontFamily: familyFor(s.family, s.weight),
    fontSize: s.size,
    lineHeight: s.lineHeight,
    letterSpacing: s.tracking,
    // fontWeight is still set so the style reads correctly if a fallback system
    // font is substituted before Manrope/Clash finish loading.
    fontWeight: String(s.weight) as TextStyle["fontWeight"],
  };
}

export const type: Record<ScaleKey, TextStyle> = {
  displayXl: build("displayXl"),
  displayLg: build("displayLg"),
  displayMd: build("displayMd"),
  titleLg: build("titleLg"),
  titleMd: build("titleMd"),
  body: build("body"),
  bodySm: build("bodySm"),
  label: build("label"),
  caption: build("caption"),
  overline: build("overline"),
};

/** Apply to any numeric that animates or is compared so digit width is fixed. */
export const tabular: TextStyle = { fontVariant: ["tabular-nums"] };

/** overline is an all-caps eyebrow — the casing is part of the token's intent. */
export const overlineCaps: TextStyle = { ...type.overline, textTransform: "uppercase" };
