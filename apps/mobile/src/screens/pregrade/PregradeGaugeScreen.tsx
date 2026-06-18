import { useEffect } from "react";
import { AccessibilityInfo, ScrollView, StyleSheet, View } from "react-native";

import type { PregradeEstimate } from "@/api";
import { Button, Screen, Skeleton, Text } from "@/components";
import { useTheme } from "@/theme";
import { GaugeArc } from "./GaugeArc";
import { SubScoreRow } from "./SubScoreRow";
import {
  ACTION_LOG_GRADE,
  ACTION_WHAT_AFFECTS,
  COMPUTING_OVERLINE,
  COMPUTING_SUB,
  COMPUTING_TITLE,
  ERROR_RETRY,
  ERROR_SUB,
  ERROR_TITLE,
  GAUGE_OVERLINE,
  NON_AFFILIATION,
  SUBSCORES_HEADING,
  SURFACE_CAVEAT,
  confidenceLine,
} from "./copy";
import {
  confidencePercent,
  gaugeA11y,
  verdictFor,
  verdictLine,
  type VerdictTone,
} from "./gauge";

// The signature trust screen (gauge spec). It renders an honest answer to "is this worth
// grading?" — a probability *band* with four provenance-tagged sub-scores, an overall
// confidence, and a persistent disclaimer — and never a single absolute grade. The
// verdict color is teal / amber / neutral, never red: a low estimate is a calm "hold off",
// not an alarm. The disclaimer sits in the reading order near the verdict, not as fine print.
export function PregradeGaugeScreen({
  estimate,
  onLogGrade,
  onWhatAffects,
  onBack,
}: {
  estimate: PregradeEstimate;
  onLogGrade?: () => void;
  onWhatAffects?: () => void;
  onBack?: () => void;
}) {
  const theme = useTheme();
  const { range, subScores, confidence, disclaimer } = estimate;
  const verdict = verdictFor(range);
  const surfaceLimited = subScores.some((s) => s.axis === "surface" && s.provenance === "limited");

  // Announce the range + verdict + confidence once, politely — the SR user gets the honest
  // headline immediately rather than waiting on the arc draw.
  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(gaugeA11y(range, verdict, confidence));
  }, [range, verdict, confidence]);

  return (
    <Screen ground="vault" edges={["top", "bottom"]}>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          {
            padding: theme.space["6"],
            paddingTop: theme.space["8"],
            gap: theme.space["7"],
          },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topbar}>
          <Text
            variant="label"
            tone="secondary"
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Back"
          >
            ‹ Back
          </Text>
        </View>

        {/* Verdict header — the range and the recommendation read as one line. */}
        <View style={{ gap: theme.space["2"] }} accessibilityRole="header">
          <Text variant="overline" tone="tertiary">
            {GAUGE_OVERLINE}
          </Text>
          <VerdictLine range={range} />
        </View>

        {/* Gauge — the band, not a needle. */}
        <View style={{ gap: theme.space["2"] }}>
          <GaugeArc range={range} />
          <Text variant="caption" tone="tertiary" style={styles.confidence}>
            {confidenceLine(confidencePercent(confidence))}
          </Text>
        </View>

        {/* Sub-scores. */}
        <View style={{ gap: theme.space["5"] }}>
          <Text variant="overline" tone="tertiary">
            {SUBSCORES_HEADING}
          </Text>
          <View style={{ gap: theme.space["5"] }}>
            {subScores.map((sub, i) => (
              <SubScoreRow key={sub.axis} sub={sub} index={i} />
            ))}
          </View>
        </View>

        {surfaceLimited ? <SurfaceCaveat /> : null}

        <View style={{ gap: theme.space["3"] }}>
          <Button
            label={ACTION_LOG_GRADE}
            tier="secondary"
            onPress={onLogGrade}
            accessibilityHint="Records the official grade once you get it back — improves future estimates."
          />
          <Button label={ACTION_WHAT_AFFECTS} tier="tertiary" onPress={onWhatAffects} />
        </View>

        {/* Disclaimer — persistent, never dismissible, in the reading order. */}
        <Text
          variant="caption"
          tone="tertiary"
          style={[styles.disclaimer, { borderTopColor: theme.color.border, paddingTop: theme.space["5"] }]}
        >
          {`${disclaimer} ${NON_AFFILIATION}`}
        </Text>
      </ScrollView>
    </Screen>
  );
}

const VERDICT_TONE_COLOR: Record<VerdictTone, "lock" | "primary"> = {
  worth: "lock",
  borderline: "primary",
  hold: "primary",
};

// The verdict reads as one display line; the recommendation phrase is colored (teal for
// worth) but always carries the word too — color is never the sole signal. Borderline and
// hold use amber/neutral via an inline color, never red.
function VerdictLine({ range }: { range: PregradeEstimate["range"] }) {
  const theme = useTheme();
  const verdict = verdictFor(range);
  const recColor =
    verdict.tone === "worth"
      ? theme.color.lock
      : verdict.tone === "borderline"
        ? theme.color.amber
        : theme.color.textSecondary;
  return (
    <Text
      variant="displayMd"
      tone={VERDICT_TONE_COLOR[verdict.tone]}
      tabular
      accessibilityLabel={verdictLine(range, verdict)}
    >
      {`Likely ${range.likelyLow === range.likelyHigh ? range.likelyLow : `${range.likelyLow}–${range.likelyHigh}`} · `}
      <Text variant="displayMd" style={{ color: recColor }} tabular>
        {verdict.label}
      </Text>
    </Text>
  );
}

function SurfaceCaveat() {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.caveat,
        {
          backgroundColor: theme.color.amberSoft,
          borderLeftColor: theme.color.amber,
          borderRadius: theme.radius.sm,
          paddingVertical: theme.space["4"],
          paddingHorizontal: theme.space["5"],
        },
      ]}
      accessibilityRole="text"
    >
      <Text variant="bodySm" style={{ color: theme.color.onAmber }}>
        {SURFACE_CAVEAT}
      </Text>
    </View>
  );
}

// Computing — gauge area is a pulsing skeleton, sub-scores are skeleton bars, header is
// honest staged copy. No fake progress bar (spec §51).
export function PregradeComputing() {
  const theme = useTheme();
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View
        style={[styles.computing, { gap: theme.space["7"], paddingTop: theme.space["9"] }]}
        accessibilityLiveRegion="polite"
        accessibilityLabel={`${COMPUTING_TITLE} ${COMPUTING_SUB}`}
      >
        <View style={{ gap: theme.space["2"] }}>
          <Text variant="overline" tone="tertiary">
            {COMPUTING_OVERLINE}
          </Text>
          <Text variant="displayMd" tone="primary">
            {COMPUTING_TITLE}
          </Text>
          <Text variant="bodySm" tone="tertiary">
            {COMPUTING_SUB}
          </Text>
        </View>

        <View style={styles.computingGauge}>
          <Skeleton width="86%" height={120} radius={theme.radius.lg} />
        </View>

        <View style={{ gap: theme.space["5"] }}>
          {[0, 1, 2, 3].map((i) => (
            <View key={i} style={{ gap: theme.space["3"] }}>
              <Skeleton width={96} height={14} radius={theme.radius.xs} />
              <Skeleton width="100%" height={8} radius={theme.radius.pill} />
            </View>
          ))}
        </View>
      </View>
    </Screen>
  );
}

// Model/network failure (spec §55). The credit isn't consumed on failure — the copy says
// so — and the only path forward is a calm retry.
export function PregradeError({ onRetry, onBack }: { onRetry?: () => void; onBack?: () => void }) {
  const theme = useTheme();
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.computing, { gap: theme.space["7"], paddingTop: theme.space["9"] }]}>
        <View style={styles.topbar}>
          <Text
            variant="label"
            tone="secondary"
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Back"
          >
            ‹ Back
          </Text>
        </View>
        <View style={[styles.spacer, { gap: theme.space["3"], justifyContent: "center" }]}>
          <Text variant="displayMd" tone="primary">
            {ERROR_TITLE}
          </Text>
          <Text variant="bodySm" tone="tertiary">
            {ERROR_SUB}
          </Text>
        </View>
        <Button label={ERROR_RETRY} tier="primary" onPress={onRetry} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
  },
  spacer: {
    flex: 1,
  },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
  },
  confidence: {
    textAlign: "center",
  },
  disclaimer: {
    borderTopWidth: 1,
  },
  caveat: {
    borderLeftWidth: 3,
  },
  computing: {
    flex: 1,
  },
  computingGauge: {
    alignItems: "center",
  },
});
