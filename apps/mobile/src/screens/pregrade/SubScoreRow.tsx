import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";

import type { SubScore } from "@/api";
import { Text } from "@/components";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { subScoreA11y, subScoreValue } from "./gauge";
import { AXIS_LABEL, PROVENANCE_TAG } from "./copy";

type Props = {
  sub: SubScore;
  /** Stagger index — meters fill top→bottom, 60ms apart (spec §38). */
  index: number;
};

// A meter past its midpoint in the weak zone tints toward amber — informative, never
// alarming red (spec §25). The threshold is the meter's own midpoint, not a pass/fail line.
const WEAK_THRESHOLD = 5;

// One axis row: label + provenance tag, a thin 0–10 meter, and the tabular value. The
// `measured`/`estimated`/`limited` tag shows how the axis was assessed — provenance is
// part of the honest claim, not decoration.
export function SubScoreRow({ sub, index }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const fraction = Math.max(0, Math.min(1, sub.score / 10));
  const weak = sub.score < WEAK_THRESHOLD;
  const fillColor = weak ? theme.color.amber : theme.color.accent;

  const grow = useSharedValue(reduceMotion ? 1 : 0);
  useEffect(() => {
    grow.value = reduceMotion
      ? 1
      : withDelay(index * 60, withTiming(1, { duration: theme.motion.duration.base }));
  }, [reduceMotion, grow, index, theme.motion.duration.base]);

  const fillStyle = useAnimatedStyle(() => ({
    width: `${grow.value * fraction * 100}%`,
  }));

  return (
    <View
      style={[styles.row, { gap: theme.space["3"] }]}
      accessibilityRole="text"
      accessibilityLabel={subScoreA11y(sub)}
    >
      <View style={[styles.top, { gap: theme.space["3"] }]}>
        <Text variant="bodySm" tone="primary" style={styles.label}>
          {AXIS_LABEL[sub.axis]}
        </Text>
        <ProvenanceTag sub={sub} />
      </View>

      <View style={[styles.meterRow, { gap: theme.space["4"] }]}>
        <View
          style={[
            styles.meter,
            { backgroundColor: theme.color.bgInset, borderRadius: theme.radius.pill },
          ]}
          accessibilityElementsHidden
          importantForAccessibility="no"
        >
          <Animated.View
            style={[styles.fill, { backgroundColor: fillColor, borderRadius: theme.radius.pill }, fillStyle]}
          />
        </View>
        <Text variant="bodySm" tone="secondary" tabular style={styles.value}>
          {subScoreValue(sub)}
        </Text>
      </View>
    </View>
  );
}

function ProvenanceTag({ sub }: { sub: SubScore }) {
  const theme = useTheme();
  const { provenance } = sub;
  const palette =
    provenance === "measured"
      ? { fg: theme.color.vaultTeal, bg: withAlpha(theme.color.vaultTeal, 0.14) }
      : provenance === "limited"
        ? { fg: theme.color.amber, bg: theme.color.amberSoft }
        : { fg: theme.color.textTertiary, bg: theme.color.bgRaised };
  return (
    <View
      style={[
        styles.tag,
        { backgroundColor: palette.bg, borderRadius: theme.radius.pill },
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      <Text variant="overline" style={{ color: palette.fg }}>
        {PROVENANCE_TAG[provenance]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    alignSelf: "stretch",
  },
  top: {
    flexDirection: "row",
    alignItems: "center",
  },
  label: {
    fontWeight: "600",
  },
  meterRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  meter: {
    flex: 1,
    height: 8,
    overflow: "hidden",
  },
  fill: {
    height: "100%",
  },
  value: {
    minWidth: 64,
    textAlign: "right",
  },
  tag: {
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
});
