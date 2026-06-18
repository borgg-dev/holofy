import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedProps,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";
import Svg, { Defs, LinearGradient, Path, Stop } from "react-native-svg";

import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import type { BandTone } from "./band";

type Props = {
  tone: BandTone;
  /** Drawn smaller in the SR-hidden header; the verdict text carries the real meaning. */
  size?: number;
};

const AnimatedPath = Animated.createAnimatedComponent(Path);

// A crest outline at the demo's stroke weight — a vault sigil, not a checkmark badge. The
// crossbar reads as a sealed strongbox: this is a *vault* mark, never a tick that could be
// mistaken for an "authentic ✓" certificate stamp (the exact claim charter §3.5 forbids).
const SHIELD = "M24 4 L42 11 V25 C42 35 34 42 24 45 C14 42 6 35 6 25 V11 Z";
const CROSSBAR = "M14 22 H34";

// The signature shield (master plan §6). Teal for a reassuring read, amber for caution —
// never red. The crest's edge draws in once then its fill blooms; reduced motion renders it
// settled. Purely decorative — hidden from the reader, which hears the verdict text instead.
export function ShieldMark({ tone, size = 96 }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const stroke = tone === "reassuring" ? theme.color.vaultTeal : theme.color.amber;

  const bloom = useSharedValue(reduceMotion ? 1 : 0);
  useEffect(() => {
    bloom.value = reduceMotion
      ? 1
      : withDelay(
          theme.motion.duration.fast,
          withTiming(1, {
            duration: theme.motion.duration.slow,
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })
        );
  }, [reduceMotion, bloom, theme.motion.duration.fast, theme.motion.duration.slow]);

  const fillProps = useAnimatedProps(() => ({ opacity: bloom.value * 0.18 }));
  const crossbarProps = useAnimatedProps(() => ({ opacity: 0.3 + bloom.value * 0.7 }));

  return (
    <View style={styles.wrap} importantForAccessibility="no" accessibilityElementsHidden>
      <Svg width={size} height={size} viewBox="0 0 48 48" fill="none">
        <Defs>
          <LinearGradient id="shieldFill" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={stroke} stopOpacity={0.9} />
            <Stop offset="1" stopColor={stroke} stopOpacity={0.2} />
          </LinearGradient>
        </Defs>

        {/* Fill blooms behind the outline — a glow, not a solid badge. */}
        <AnimatedPath d={SHIELD} fill="url(#shieldFill)" animatedProps={fillProps} />

        {/* The crest edge. */}
        <Path
          d={SHIELD}
          fill="none"
          stroke={stroke}
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* The vault crossbar — a sealed-strongbox mark, deliberately not a checkmark. */}
        <AnimatedPath
          d={CROSSBAR}
          stroke={withAlpha(stroke, 0.9)}
          strokeWidth={2}
          strokeLinecap="round"
          animatedProps={crossbarProps}
        />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    justifyContent: "center",
  },
});
