import { Pressable, StyleSheet, View, type ViewStyle } from "react-native";

import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

type Tier = "primary" | "secondary" | "tertiary";

type Props = {
  label: string;
  onPress?: () => void;
  tier?: Tier;
  disabled?: boolean;
  /** Renders an inline spinner-dot row and disables; for in-flight actions. */
  busy?: boolean;
  /** A destructive action (delete/remove): swaps the accent for the error red. */
  destructive?: boolean;
  accessibilityHint?: string;
  style?: ViewStyle;
};

// The action primitive per foil-reveal.md: primary is an accent fill (52pt), secondary
// a 1.5px accent outline, tertiary text-only. Not a default RN <Button> anywhere —
// these carry the Vault's press/disabled/busy states and the token radius/spacing.
export function Button({
  label,
  onPress,
  tier = "primary",
  disabled = false,
  busy = false,
  destructive = false,
  accessibilityHint,
  style,
}: Props) {
  const theme = useTheme();
  const inactive = disabled || busy;
  const primary = tier === "primary";
  // A destructive action recolors the accent to the error red, keeping the same tier shapes.
  const fill = destructive ? theme.color.errorRed : theme.color.accent;
  const fillPressed = destructive ? withAlpha(theme.color.errorRed, 0.82) : theme.color.accentPressed;

  return (
    <Pressable
      onPress={inactive ? undefined : onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy }}
      style={({ pressed }) => [
        styles.base,
        {
          minHeight: primary ? 52 : theme.tapTarget,
          borderRadius: theme.radius.md,
          paddingHorizontal: theme.space["6"],
          opacity: inactive ? 0.45 : 1,
        },
        tier === "primary" && {
          backgroundColor: pressed ? fillPressed : fill,
        },
        tier === "secondary" && {
          borderWidth: 1.5,
          borderColor: fill,
          backgroundColor: pressed ? withAlpha(fill, 0.12) : "transparent",
        },
        tier === "tertiary" && {
          backgroundColor: pressed ? withAlpha(theme.color.textPrimary, 0.06) : "transparent",
        },
        style,
      ]}
    >
      <View style={styles.row}>
        {busy ? <BusyDots /> : null}
        <Text
          variant={primary ? "titleMd" : "label"}
          tone={primary ? "onAccent" : tier === "secondary" ? "accent" : "secondary"}
          style={destructive && !primary ? { color: theme.color.errorRed } : undefined}
        >
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

// Three static dots rather than a spinning ring — quieter, on-brand, and no animation
// dependency for a transient state. Decorative, so hidden from the reader.
function BusyDots() {
  const theme = useTheme();
  return (
    <View style={styles.dots} importantForAccessibility="no" accessibilityElementsHidden>
      {[0, 1, 2].map((i) => (
        <View
          key={i}
          style={[styles.dot, { backgroundColor: theme.color.textOnAccent, opacity: 0.5 + i * 0.2 }]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  base: { alignItems: "center", justifyContent: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  dots: { flexDirection: "row", gap: 4 },
  dot: { width: 5, height: 5, borderRadius: 3 },
});
