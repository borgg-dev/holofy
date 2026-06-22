import { useState } from "react";
import { LayoutChangeEvent, Pressable, StyleSheet, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";

import { DISPLAY_CURRENCIES, type DisplayCurrency } from "@/currency";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

const LABELS: Record<DisplayCurrency, string> = { EUR: "€ EUR", USD: "$ USD" };

type Props = {
  value: DisplayCurrency;
  onChange: (currency: DisplayCurrency) => void;
};

// The display-currency segmented control — the same inset track + sliding violet thumb as the
// appearance toggle, so the two settings read as siblings. EUR is the source of truth; USD is a
// converted view (the disclosure beneath it says so).
export function CurrencyToggle({ value, onChange }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const [trackWidth, setTrackWidth] = useState(0);

  const inset = 3;
  const segmentWidth = trackWidth > 0 ? (trackWidth - inset * 2) / DISPLAY_CURRENCIES.length : 0;
  const activeIndex = Math.max(0, DISPLAY_CURRENCIES.indexOf(value));

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
      accessibilityLabel="Display currency"
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

      {DISPLAY_CURRENCIES.map((currency) => {
        const selected = currency === value;
        return (
          <Pressable
            key={currency}
            onPress={() => onChange(currency)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            accessibilityLabel={LABELS[currency]}
            style={styles.segment}
          >
            <Text variant="label" tone={selected ? "onAccent" : "secondary"}>
              {LABELS[currency]}
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
