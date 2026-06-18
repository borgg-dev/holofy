import { useState } from "react";
import { LayoutChangeEvent, Pressable, StyleSheet, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import type { ThemeMode } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

type Option = { mode: ThemeMode; label: string };

const OPTIONS: readonly Option[] = [
  { mode: "system", label: "System" },
  { mode: "light", label: "Light" },
  { mode: "dark", label: "Dark" },
];

type Props = {
  value: ThemeMode;
  onChange: (mode: ThemeMode) => void;
};

// The appearance segmented control. Three even segments inside an inset track; a single violet
// thumb slides under the active label so the brand accent — not a stock switch — marks the
// choice. The thumb width is measured rather than assumed so the geometry holds across locales
// and screen widths. Reduced motion snaps the thumb instead of sliding it.
export function AppearanceToggle({ value, onChange }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const [trackWidth, setTrackWidth] = useState(0);

  const inset = 3;
  const segmentWidth = trackWidth > 0 ? (trackWidth - inset * 2) / OPTIONS.length : 0;
  const activeIndex = Math.max(0, OPTIONS.findIndex((o) => o.mode === value));

  const offset = useSharedValue(0);
  offset.value = reduceMotion
    ? activeIndex * segmentWidth
    : withTiming(activeIndex * segmentWidth, { duration: theme.motion.duration.base });

  const thumbStyle = useAnimatedStyle(() => ({
    width: segmentWidth,
    transform: [{ translateX: offset.value }],
  }));

  const onTrackLayout = (e: LayoutChangeEvent) => setTrackWidth(e.nativeEvent.layout.width);

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel="Appearance"
      onLayout={onTrackLayout}
      style={[
        styles.track,
        {
          padding: inset,
          backgroundColor: theme.color.bgInset,
          borderColor: theme.color.border,
          borderRadius: theme.radius.pill,
        },
      ]}
    >
      {segmentWidth > 0 ? (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.thumb,
            {
              backgroundColor: theme.color.accent,
              borderRadius: theme.radius.pill,
              shadowColor: withAlpha(theme.color.accent, 0.6),
            },
            thumbStyle,
          ]}
        />
      ) : null}

      {OPTIONS.map((option) => {
        const selected = option.mode === value;
        return (
          <Pressable
            key={option.mode}
            onPress={() => onChange(option.mode)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={option.label}
            style={styles.segment}
          >
            <Text variant="label" tone={selected ? "onAccent" : "secondary"}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    borderWidth: StyleSheet.hairlineWidth,
    position: "relative",
  },
  thumb: {
    position: "absolute",
    top: 3,
    left: 3,
    bottom: 3,
    shadowOpacity: 0.5,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  segment: {
    flex: 1,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
  },
});
