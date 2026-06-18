import { type TextStyle } from "react-native";

import { Text } from "./Text";

type Props = {
  /** Amount in major units (euros, not cents). */
  amount: number;
  currency?: string;
  /** Locale drives grouping/decimal marks — EU default formats €1.234,56. */
  locale?: string;
  variant?: "displayXl" | "displayLg" | "displayMd" | "titleLg" | "body";
  tone?: "primary" | "reward" | "secondary";
  style?: TextStyle;
};

// The price primitive. Always Intl-formatted for the locale (the German collector
// reads €1.234,56, not $1,234.56) and always tabular so a count-up animation
// doesn't shift digits. This is the wedge's number — it never renders raw.
export function ValueText({
  amount,
  currency = "EUR",
  locale = "de-DE",
  variant = "displayMd",
  tone = "primary",
  style,
}: Props) {
  const formatted = formatCurrency(amount, currency, locale);
  return (
    <Text
      variant={variant}
      tone={tone}
      tabular
      style={style}
      accessibilityLabel={formatted}
      allowFontScaling
    >
      {formatted}
    </Text>
  );
}

function formatCurrency(amount: number, currency: string, locale: string): string {
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(amount);
  } catch {
    // Hermes ships Intl, but guard a missing locale build so a price still renders.
    return `${currency} ${amount.toFixed(2)}`;
  }
}
