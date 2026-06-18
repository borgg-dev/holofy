import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  cancelAnimation,
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";

type Props = {
  locked: boolean;
  /** Frame width as a fraction of the available width; height follows card ratio. */
  widthPct?: number;
};

const BRACKET = 32; // arm length of each corner bracket
const STROKE_SEARCHING = 1.5;
const STROKE_LOCKED = 2.5;

// The capture target: four corner brackets, never a full rectangle — lighter,
// more instrument than viewfinder. Searching it breathes (1.0→1.015) with a
// dashed neutral stroke; on lock it snaps (1.04→1.0 spring) to a solid violet
// stroke (the brand capture hue) and a violet aura fades in. Reduced motion keeps
// the color/glow change (state legibility) but drops the breathe and the scale snap.
export function ScanFrame({ locked, widthPct = 0.62 }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const lock = useSharedValue(locked ? 1 : 0); // 0 searching … 1 locked
  const breathe = useSharedValue(0);
  const snap = useSharedValue(1);

  // Breathing loop while searching.
  useEffect(() => {
    if (locked || reduceMotion) {
      cancelAnimation(breathe);
      breathe.value = 0;
      return;
    }
    breathe.value = withRepeat(
      withTiming(1, { duration: 1600, easing: Easing.bezier(0.2, 0, 0, 1) }),
      -1,
      true
    );
    return () => cancelAnimation(breathe);
  }, [locked, reduceMotion, breathe]);

  // Lock state crossfade + the spring snap on the locking edge.
  useEffect(() => {
    lock.value = reduceMotion
      ? locked
        ? 1
        : 0
      : withTiming(locked ? 1 : 0, { duration: theme.motion.duration.base });
    if (locked && !reduceMotion) {
      snap.value = withSequence(
        withTiming(1.04, { duration: 0 }),
        withTiming(1, { duration: theme.motion.duration.base, easing: Easing.bezier(0.34, 1.56, 0.64, 1) })
      );
    } else {
      snap.value = 1;
    }
  }, [locked, reduceMotion, lock, snap, theme.motion.duration.base]);

  const frameStyle = useAnimatedStyle(() => {
    const breatheScale = 1 + breathe.value * 0.015;
    return { transform: [{ scale: breatheScale * snap.value }] };
  });

  const glowStyle = useAnimatedStyle(() => ({ opacity: lock.value }));

  const searching = theme.color.textTertiary; // calm neutral while hunting
  const lockColor = theme.color.lock;

  // Only the color crossfades continuously; the stroke width steps with the lock
  // edge (1.5→2.5px), which Reanimated can't tween per-side without clobbering the
  // bracket's zeroed sides, and the eye reads the snap as one event anyway.
  const cornerColorStyle = useAnimatedStyle(() => ({
    borderColor: interpolateColor(lock.value, [0, 1], [searching, lockColor]),
  }));

  const stroke = locked ? STROKE_LOCKED : STROKE_SEARCHING;
  const corners = [
    { key: "tl", style: cornerStyle(theme.radius.sm, stroke).tl },
    { key: "tr", style: cornerStyle(theme.radius.sm, stroke).tr },
    { key: "bl", style: cornerStyle(theme.radius.sm, stroke).bl },
    { key: "br", style: cornerStyle(theme.radius.sm, stroke).br },
  ] as const;

  return (
    <View
      pointerEvents="none"
      style={[styles.wrap, { width: `${widthPct * 100}%`, aspectRatio: theme.cardRatio }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Animated.View
        style={[
          StyleSheet.absoluteFill,
          styles.glow,
          { backgroundColor: withAlpha(lockColor, 0.18), borderRadius: 9999 },
          glowStyle,
        ]}
      />
      <Animated.View style={[StyleSheet.absoluteFill, frameStyle]}>
        {corners.map(({ key, style }) => (
          <Animated.View
            key={key}
            // Searching uses a dashed stroke; locked is solid. Reanimated can't
            // animate borderStyle, so it flips discretely with the lock state.
            style={[styles.corner, style, { borderStyle: locked ? "solid" : "dashed" }, cornerColorStyle]}
          />
        ))}
      </Animated.View>
    </View>
  );
}

// Each corner shows only two of its four borders (an L), so the frame reads as
// brackets, not a box. Built per-corner with explicit per-side widths so the
// hidden sides stay at 0 regardless of the animated color layer above.
function cornerStyle(r: number, w: number) {
  const base = { position: "absolute" as const, width: BRACKET, height: BRACKET };
  return {
    tl: { ...base, top: 0, left: 0, borderTopWidth: w, borderLeftWidth: w, borderTopLeftRadius: r },
    tr: { ...base, top: 0, right: 0, borderTopWidth: w, borderRightWidth: w, borderTopRightRadius: r },
    bl: { ...base, bottom: 0, left: 0, borderBottomWidth: w, borderLeftWidth: w, borderBottomLeftRadius: r },
    br: { ...base, bottom: 0, right: 0, borderBottomWidth: w, borderRightWidth: w, borderBottomRightRadius: r },
  };
}

const styles = StyleSheet.create({
  wrap: { alignItems: "center", justifyContent: "center" },
  glow: { transform: [{ scaleX: 1.25 }, { scaleY: 1.1 }] },
  corner: {},
});
