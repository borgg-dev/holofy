import { useEffect } from "react";
import { Pressable, StyleSheet } from "react-native";
import Animated, {
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import { type } from "@/theme/typography";

type Props = {
  locked: boolean;
  label: string;
  /** Caller decides what an early (sub-threshold) tap does — usually a coaching toast. */
  onPress: () => void;
  /** Signals an external refuse so the pill shakes (e.g. the user tapped while unlocked). */
  refuseSignal?: number;
};

// Not a round shutter button — a thin teal-outlined pill that fills teal on lock.
// At rest it reads "Hold steady" (disabled); locked it becomes "Capture". An early
// tap doesn't fail silently: the pill shakes ±4px twice so the refusal is felt.
export function Shutter({ locked, label, onPress, refuseSignal = 0 }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const fill = useSharedValue(locked ? 1 : 0);
  const shakeX = useSharedValue(0);

  useEffect(() => {
    fill.value = reduceMotion
      ? locked
        ? 1
        : 0
      : withTiming(locked ? 1 : 0, { duration: theme.motion.duration.base });
  }, [locked, reduceMotion, fill, theme.motion.duration.base]);

  useEffect(() => {
    if (refuseSignal === 0 || reduceMotion) return;
    shakeX.value = withSequence(
      withTiming(-4, { duration: 45 }),
      withTiming(4, { duration: 45 }),
      withTiming(-4, { duration: 45 }),
      withTiming(0, { duration: 45 })
    );
  }, [refuseSignal, reduceMotion, shakeX]);

  const containerStyle = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(fill.value, [0, 1], ["transparent", theme.color.lock]),
    borderColor: interpolateColor(fill.value, [0, 1], [theme.color.lock, theme.color.lock]),
    transform: [{ translateX: shakeX.value }],
  }));

  const labelStyle = useAnimatedStyle(() => ({
    color: interpolateColor(fill.value, [0, 1], [theme.color.textPrimary, theme.color.bg]),
  }));

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={locked ? `Capture. ${label}` : "Hold steady"}
      accessibilityHint={locked ? undefined : "Align the card until all three quality checks pass."}
      accessibilityState={{ disabled: !locked }}
      style={styles.press}
    >
      <Animated.View
        style={[
          styles.pill,
          { borderRadius: theme.radius.pill, minHeight: 56 },
          containerStyle,
        ]}
      >
        <Animated.Text style={[type.label, styles.label, labelStyle]}>{label}</Animated.Text>
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  press: { width: "78%" },
  pill: {
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  label: { fontWeight: "600", textTransform: "none" },
});
