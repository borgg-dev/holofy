import { useEffect } from "react";
import { StyleSheet } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import { Text } from "./Text";

type Props = {
  /** Null hides the toast. A message string shows it and announces it politely. */
  message: string | null;
};

// The refuse-to-grade coaching line. Amber left-rule, never red — a bad photo is
// a coaching state, not the user's fault. Announced as a polite live region so a
// screen-reader user hears why capture was held.
export function CoachingToast({ message }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const shown = message != null;

  const progress = useSharedValue(0);
  useEffect(() => {
    progress.value = reduceMotion
      ? shown
        ? 1
        : 0
      : withTiming(shown ? 1 : 0, { duration: theme.motion.duration.base });
  }, [shown, reduceMotion, progress, theme.motion.duration.base]);

  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: (1 - progress.value) * 6 }],
  }));

  return (
    <Animated.View
      pointerEvents="none"
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[
        styles.toast,
        {
          backgroundColor: theme.color.amberSoft,
          borderLeftColor: theme.color.amber,
          borderRadius: theme.radius.sm,
          paddingVertical: theme.space["4"],
          paddingHorizontal: theme.space["5"],
        },
        style,
      ]}
    >
      <Text variant="bodySm" style={{ color: theme.color.onAmber }}>
        {message ?? ""}
      </Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    borderLeftWidth: 3,
  },
});
