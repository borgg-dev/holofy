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

import type { GradeProbabilityRange } from "@/api";
import { useReduceMotion, useTheme } from "@/theme";
import { type as typeScale } from "@/theme/typography";
import { Text } from "@/components";
import {
  GAUGE,
  arcPath,
  formatScore,
  gradeFraction,
  modalGrade,
  pointAtFraction,
} from "./gauge";
import { GAUGE_MODAL_LABEL } from "./copy";

type Props = {
  range: GradeProbabilityRange;
};

const AnimatedPath = Animated.createAnimatedComponent(Path);

const TICK_INNER = 84;
const TICK_OUTER = 80;
const TICK_OUTER_TEN = 76;
const TRACK_STROKE = 10;
const BAND_STROKE = 11;

// The gauge: a 200° arc over grades 1→10 where the predicted band is painted as a
// luminous violet→teal band, never a needle on a single value — the uncertainty *is*
// the message (gauge spec §5). The band draws clockwise then blooms; reduced motion
// renders it filled at once. The bright modal grade sits at the band's core as text, the
// only number on screen, and even it is hedged ("modal", inside a range).
export function GaugeArc({ range }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const trackPath = arcPath(GAUGE.minGrade, GAUGE.maxGrade);
  const bandPath = arcPath(range.likelyLow, range.likelyHigh);
  const modal = modalGrade(range);
  const modalPoint = pointAtFraction(gradeFraction(modal));

  const bloom = useSharedValue(reduceMotion ? 1 : 0);
  useEffect(() => {
    bloom.value = reduceMotion
      ? 1
      : withDelay(
          theme.motion.duration.slow,
          withTiming(1, { duration: theme.motion.duration.base, easing: Easing.bezier(0.16, 1, 0.3, 1) })
        );
  }, [reduceMotion, bloom, theme.motion.duration.slow, theme.motion.duration.base]);

  const bandAnimatedProps = useAnimatedProps(() => ({
    opacity: 0.55 + bloom.value * 0.4,
    strokeWidth: BAND_STROKE * (0.85 + bloom.value * 0.15),
  }));

  const ticks = Array.from({ length: 10 }, (_, i) => i + 1);

  return (
    <View style={styles.wrap}>
      <Svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${GAUGE.viewBox.width} ${GAUGE.viewBox.height}`}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <Defs>
          <LinearGradient id="gaugeBand" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0" stopColor={theme.color.holoViolet} />
            <Stop offset="1" stopColor={theme.color.vaultTeal} />
          </LinearGradient>
        </Defs>

        <Path
          d={trackPath}
          fill="none"
          stroke={theme.color.border}
          strokeWidth={TRACK_STROKE}
          strokeLinecap="round"
        />

        {ticks.map((g) => {
          const p = pointAtFraction(gradeFraction(g));
          const a = Math.atan2(p.y - GAUGE.center.y, p.x - GAUGE.center.x);
          const isTen = g === 10;
          const outer = isTen ? TICK_OUTER_TEN : TICK_OUTER;
          return (
            <Path
              key={g}
              d={`M ${GAUGE.center.x + Math.cos(a) * outer} ${
                GAUGE.center.y + Math.sin(a) * outer
              } L ${GAUGE.center.x + Math.cos(a) * (TICK_INNER + 6)} ${
                GAUGE.center.y + Math.sin(a) * (TICK_INNER + 6)
              }`}
              stroke={isTen ? theme.color.textSecondary : theme.color.borderStrong}
              strokeWidth={isTen ? 2.4 : 2}
              strokeLinecap="round"
            />
          );
        })}

        <AnimatedPath
          d={bandPath}
          fill="none"
          stroke="url(#gaugeBand)"
          strokeLinecap="round"
          animatedProps={bandAnimatedProps}
        />
      </Svg>

      {/* Modal grade as text, positioned at the band core. The only numeral on the
          screen — and it's labelled "modal" inside a range, never "the grade". */}
      <View
        pointerEvents="none"
        style={[
          styles.modal,
          {
            left: `${(modalPoint.x / GAUGE.viewBox.width) * 100}%`,
            top: `${(GAUGE.center.y / GAUGE.viewBox.height) * 100 - 30}%`,
          },
        ]}
      >
        <Text
          style={[typeScale.titleLg, { color: theme.color.textPrimary }]}
          tabular
          accessibilityElementsHidden
          importantForAccessibility="no"
        >
          {formatScore(modal)}
        </Text>
        <Text variant="caption" tone="tertiary" accessibilityElementsHidden importantForAccessibility="no">
          {GAUGE_MODAL_LABEL}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    aspectRatio: GAUGE.viewBox.width / GAUGE.viewBox.height,
  },
  modal: {
    position: "absolute",
    alignItems: "center",
    transform: [{ translateX: -24 }],
    width: 48,
  },
});
