import { StyleSheet, View } from "react-native";

import { Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { formatTrendPercent, trendA11y, type Trend } from "./format";

type Props = {
  trend: Trend;
  /** Larger pill for the reveal hero; compact for list rows / the Vault header. */
  size?: "md" | "sm";
};

// The signed 30-day delta. Up is teal, down is amber — never red: a price dip is not an
// error (foil-reveal.md). The sign glyph + the up/down word in the a11y label mean state
// never rides on color alone.
export function TrendPill({ trend, size = "md" }: Props) {
  const theme = useTheme();
  const color =
    trend.direction === "down" ? theme.color.amber : trend.direction === "up" ? theme.color.vaultTeal : theme.color.textTertiary;

  return (
    <View
      accessibilityLabel={trendA11y(trend)}
      style={[
        styles.pill,
        {
          backgroundColor: withAlpha(color, 0.14),
          borderRadius: theme.radius.pill,
          paddingHorizontal: size === "md" ? theme.space["3"] : theme.space["2"],
          paddingVertical: size === "md" ? theme.space["1"] : 1,
        },
      ]}
    >
      <Text variant={size === "md" ? "label" : "caption"} tabular style={{ color }}>
        {formatTrendPercent(trend.fraction)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
  },
});
