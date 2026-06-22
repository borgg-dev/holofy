import { type TextStyle } from "react-native";

import { useCurrency } from "@/currency";
import { Text } from "./Text";

type Props = {
  /** Amount in major units of the SOURCE currency — EUR here (Cardmarket is the price source). */
  amount: number;
  /** Source currency of `amount`. Defaults to EUR; only EUR is converted to the display currency. */
  currency?: string;
  variant?: "displayXl" | "displayLg" | "displayMd" | "titleLg" | "titleMd" | "body";
  tone?: "primary" | "reward" | "secondary";
  style?: TextStyle;
};

// The price primitive. Prices are stored in EUR; this renders them in the collector's chosen
// display currency (a straight FX conversion — see CurrencyProvider), Intl-formatted for that
// currency's locale and always tabular so a count-up animation doesn't shift digits. This is the
// single place a price becomes text — it never renders raw.
export function ValueText({ amount, currency = "EUR", variant = "displayMd", tone = "primary", style }: Props) {
  const { format } = useCurrency();
  // EUR is the canonical source: convert+format to the display currency. A non-EUR source (none
  // today) is formatted as-is, since we hold no cross-rate for it.
  const formatted =
    currency === "EUR"
      ? format(amount)
      : new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount);
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
