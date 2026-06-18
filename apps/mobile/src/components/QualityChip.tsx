import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

/** One live capture signal. "pass" reads the brand violet (a capture-met cue); working/fail read amber — never red. */
export type ChipState = "pass" | "working" | "fail";

type Props = {
  /** SR-readable signal name, e.g. "Focus". Paired with `label` for the live label. */
  signal: string;
  label: string;
  state: ChipState;
};

// A coaching chip, not a status badge: amber means "not yet", never "error".
// The dot color crossfades on state change (kept on reduced-motion for legibility);
// the label text itself changes too, so color is never the sole signal (a11y).
export function QualityChip({ signal, label, state }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const ok = state === "pass";

  const passColor = theme.color.lock; // brand violet — capture-met
  const workColor = theme.color.amber;
  const dotColor = useSharedValue(ok ? 1 : 0);

  useEffect(() => {
    const target = ok ? 1 : 0;
    dotColor.value = reduceMotion
      ? target
      : withTiming(target, { duration: theme.motion.duration.fast });
  }, [ok, reduceMotion, dotColor, theme.motion.duration.fast]);

  const dotStyle = useAnimatedStyle(() => ({
    backgroundColor: dotColor.value > 0.5 ? passColor : workColor,
  }));

  return (
    <View
      accessibilityRole="text"
      accessibilityLabel={`${signal}: ${label}`}
      style={[
        styles.chip,
        {
          backgroundColor: withAlpha(theme.color.bgInset, 0.72),
          borderRadius: theme.radius.pill,
          paddingVertical: theme.space["3"] - 1,
          paddingLeft: theme.space["3"] + 2,
          paddingRight: theme.space["4"],
          gap: theme.space["3"],
        },
      ]}
    >
      <Animated.View style={[styles.dot, dotStyle]} />
      <Text variant="bodySm" style={[styles.label, { color: theme.color.textPrimary }]}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  label: { fontWeight: "600" },
});
