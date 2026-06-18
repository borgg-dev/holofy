import { Pressable, StyleSheet, View } from "react-native";

import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

export type CaptureMode = "scan" | "stack";

type Props = {
  value: CaptureMode;
  onChange: (mode: CaptureMode) => void;
};

const OPTIONS: { mode: CaptureMode; label: string }[] = [
  { mode: "scan", label: "Scan" },
  { mode: "stack", label: "Stack" },
];

// Segmented Scan/Stack control. The two modes carry different promises — Stack is
// value-only, no grade — so this lives in the top bar where the user sets intent
// before they shoot. Selected segment lifts onto the raised Vault surface.
export function ModeToggle({ value, onChange }: Props) {
  const theme = useTheme();
  return (
    <View
      accessibilityRole="tablist"
      accessibilityLabel="Capture mode"
      style={[
        styles.group,
        { backgroundColor: withAlpha(theme.color.bgElevated, 0.55), borderRadius: theme.radius.pill },
      ]}
    >
      {OPTIONS.map(({ mode, label }) => {
        const selected = value === mode;
        return (
          <Pressable
            key={mode}
            onPress={() => onChange(mode)}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={label}
            style={[
              styles.seg,
              {
                borderRadius: theme.radius.pill,
                backgroundColor: selected ? theme.color.bgRaised : "transparent",
                paddingHorizontal: theme.space["4"] + 2,
              },
            ]}
          >
            <Text
              variant="overline"
              tone={selected ? "primary" : "tertiary"}
            >
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { flexDirection: "row", padding: 3 },
  seg: { minHeight: 32, alignItems: "center", justifyContent: "center" },
});
