import { useEffect } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";

type Props = {
  width: ViewStyle["width"];
  height: number;
  radius?: number;
  style?: ViewStyle;
};

// A loading placeholder block that breathes a low-contrast pulse — the price block's
// "fetching" state on the reveal screen, where the card is already shown but the € value
// is in flight. Reduced motion holds a static muted fill (no pulse), still legibly a
// placeholder. Decorative: the surrounding state carries the SR text.
export function Skeleton({ width, height, radius, style }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const pulse = useSharedValue(reduceMotion ? 1 : 0);

  useEffect(() => {
    if (reduceMotion) return;
    pulse.value = withRepeat(
      withTiming(1, { duration: theme.motion.duration.slow * 2, easing: Easing.inOut(Easing.ease) }),
      -1,
      true
    );
  }, [reduceMotion, pulse, theme.motion.duration.slow]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: 0.35 + pulse.value * 0.4,
  }));

  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.base,
        {
          width,
          height,
          borderRadius: radius ?? theme.radius.sm,
          backgroundColor: withAlpha(theme.color.textTertiary, 0.5),
        },
        animatedStyle,
        style,
      ]}
    >
      <View />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  base: { overflow: "hidden" },
});
