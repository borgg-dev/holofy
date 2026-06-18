import { Text as RNText, type TextProps as RNTextProps, type TextStyle } from "react-native";

import { useTheme } from "@/theme";
import { type as typeScale, tabular as tabularStyle, overlineCaps } from "@/theme/typography";

type Variant = keyof typeof typeScale;
type Tone = "primary" | "secondary" | "tertiary" | "accent" | "reward" | "lock" | "onAccent";

type Props = RNTextProps & {
  variant?: Variant;
  tone?: Tone;
  /** Tabular figures — set on anything numeric that animates or is compared. */
  tabular?: boolean;
};

// The only text component in the app. Default-RN <Text> never ships in product
// code: this binds the token type scale and semantic tones so a screen says
// `variant="titleLg" tone="secondary"` instead of carrying loose font numbers.
export function Text({ variant = "body", tone = "primary", tabular, style, ...rest }: Props) {
  const theme = useTheme();
  const base = variant === "overline" ? overlineCaps : typeScale[variant];
  const color = toneColor(theme.color, tone);
  const composed: TextStyle = { ...base, color, ...(tabular ? tabularStyle : null) };
  return <RNText {...rest} style={[composed, style]} />;
}

function toneColor(color: ReturnType<typeof useTheme>["color"], tone: Tone): string {
  switch (tone) {
    case "secondary":
      return color.textSecondary;
    case "tertiary":
      return color.textTertiary;
    case "accent":
      return color.accent;
    case "reward":
      return color.reward;
    case "lock":
      return color.lock;
    case "onAccent":
      return color.textOnAccent;
    default:
      return color.textPrimary;
  }
}
