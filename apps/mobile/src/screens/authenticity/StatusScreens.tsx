import { useEffect } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";

import type { AuthenticityNotAssessed, AuthenticityRetake } from "@/api";
import { Button, Screen, Skeleton, Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import {
  ERROR_RETRY,
  ERROR_SUB,
  ERROR_TITLE,
  NON_AFFILIATION,
  NOT_ASSESSED_BACK,
  NOT_ASSESSED_OVERLINE,
  NOT_ASSESSED_SUB,
  NOT_ASSESSED_TITLE,
  RETAKE_ACTION,
  RETAKE_BACK,
  RETAKE_OVERLINE,
  RETAKE_SUB,
  RETAKE_TITLE,
  SCREENING_OVERLINE,
  SCREENING_SUB,
  SCREENING_TITLE,
} from "./copy";

// Screening (loading) — honest staged copy naming the signals being read, over a pulsing
// skeleton for the shield-and-breakdown shape. No fake progress bar; the work is real and
// unhurried, so the copy says what's happening rather than faking a percentage.
export function ScreeningState() {
  const theme = useTheme();
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View
        style={[styles.root, { gap: theme.space["7"], paddingTop: theme.space["3"] }]}
        accessibilityLiveRegion="polite"
        accessibilityLabel={`${SCREENING_TITLE} ${SCREENING_SUB}`}
      >
        <View style={{ gap: theme.space["2"] }}>
          <Text variant="overline" tone="tertiary">
            {SCREENING_OVERLINE}
          </Text>
          <Text variant="displayMd" tone="primary">
            {SCREENING_TITLE}
          </Text>
          <Text variant="bodySm" tone="tertiary">
            {SCREENING_SUB}
          </Text>
        </View>

        <View style={styles.shieldSkeleton}>
          <Skeleton width={96} height={96} radius={theme.radius.lg} />
        </View>

        <View style={{ gap: theme.space["5"] }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <View key={i} style={{ gap: theme.space["3"] }}>
              <Skeleton width={120} height={14} radius={theme.radius.xs} />
              <Skeleton width="100%" height={10} radius={theme.radius.pill} />
            </View>
          ))}
        </View>
      </View>
    </Screen>
  );
}

// Model / network failure. The credit isn't consumed on failure — the copy says so — and
// the only path forward is a calm retry.
export function ScreeningError({ onRetry, onBack }: { onRetry?: () => void; onBack?: () => void }) {
  const theme = useTheme();
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.root, { gap: theme.space["7"], paddingTop: theme.space["3"] }]}>
        <BackRow onBack={onBack} />
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

// Capture too poor to screen (schema's `retake`). The product won't flag a card on a shot it
// can't read, so instead of a guessed band it coaches the specific fixes and routes back to
// capture. Framed as "one more pass", amber and calm — never red, never blaming the collector.
export function ScreeningRetake({
  retake,
  onRescan,
  onBack,
}: {
  retake: AuthenticityRetake;
  onRescan?: () => void;
  onBack?: () => void;
}) {
  const theme = useTheme();

  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(`${RETAKE_TITLE}. ${retake.reasons.join(" ")}`);
  }, [retake.reasons]);

  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.root, { paddingTop: theme.space["3"], gap: theme.space["8"] }]}>
        <View style={{ gap: theme.space["3"] }} accessibilityRole="header">
          <Text variant="overline" tone="lock">
            {RETAKE_OVERLINE}
          </Text>
          <Text variant="displayMd" tone="primary">
            {RETAKE_TITLE}
          </Text>
          <Text variant="bodySm" tone="secondary">
            {RETAKE_SUB}
          </Text>
        </View>

        <View style={{ gap: theme.space["4"] }}>
          {retake.reasons.map((reason, i) => (
            <ReasonRow key={i} reason={reason} />
          ))}
        </View>

        <View style={styles.spacer} />

        <View style={{ gap: theme.space["3"] }}>
          <Button
            label={RETAKE_ACTION}
            tier="primary"
            onPress={onRescan}
            accessibilityHint="Reopens the guided capture so you can fix the shots."
          />
          <Button label={RETAKE_BACK} tier="tertiary" onPress={onBack} />
        </View>

        <Disclaimer />
      </View>
    </Screen>
  );
}

// Below the value threshold (schema's `not_assessed`). A calm, honest explanation — not a
// fake score, not a red flag: screening is reserved for cards worth faking, and this one
// sits below that line. Reassuring in tone, with the same persistent non-affiliation line.
export function ScreeningNotAssessed({
  notAssessed,
  onBack,
}: {
  notAssessed: AuthenticityNotAssessed;
  onBack?: () => void;
}) {
  const theme = useTheme();

  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(
      `${NOT_ASSESSED_TITLE}. ${NOT_ASSESSED_SUB} ${notAssessed.reasons.join(" ")}`
    );
  }, [notAssessed.reasons]);

  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.root, { paddingTop: theme.space["3"], gap: theme.space["7"] }]}>
        <View style={{ gap: theme.space["3"] }} accessibilityRole="header">
          <Text variant="overline" tone="tertiary">
            {NOT_ASSESSED_OVERLINE}
          </Text>
          <Text variant="displayMd" tone="primary">
            {NOT_ASSESSED_TITLE}
          </Text>
          <Text variant="bodySm" tone="secondary" style={styles.notAssessedSub}>
            {NOT_ASSESSED_SUB}
          </Text>
        </View>

        <View style={{ gap: theme.space["3"] }}>
          {notAssessed.reasons.map((reason, i) => (
            <View key={i} style={[styles.calmRow, { gap: theme.space["3"] }]} accessibilityRole="text">
              <View style={[styles.calmDot, { backgroundColor: theme.color.textTertiary }]} />
              <Text variant="caption" tone="tertiary" style={styles.calmText}>
                {reason}
              </Text>
            </View>
          ))}
        </View>

        <View style={styles.spacer} />

        <Button label={NOT_ASSESSED_BACK} tier="secondary" onPress={onBack} />

        <Disclaimer />
      </View>
    </Screen>
  );
}

// A coaching reason on an amber-ruled row — the same coaching voice as the scan frame's
// refuse-to-screen toast, so the system speaks consistently.
function ReasonRow({ reason }: { reason: string }) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.reason,
        {
          backgroundColor: withAlpha(theme.color.amber, 0.08),
          borderLeftColor: theme.color.amber,
          borderRadius: theme.radius.sm,
          paddingVertical: theme.space["4"],
          paddingHorizontal: theme.space["5"],
          gap: theme.space["3"],
        },
      ]}
      accessibilityRole="text"
    >
      <View style={[styles.dot, { backgroundColor: theme.color.amber }]} />
      <Text variant="bodySm" tone="secondary" style={styles.reasonText}>
        {reason}
      </Text>
    </View>
  );
}

function BackRow({ onBack }: { onBack?: () => void }) {
  return (
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
  );
}

function Disclaimer() {
  const theme = useTheme();
  return (
    <Text
      variant="caption"
      tone="tertiary"
      style={[styles.disclaimer, { borderTopColor: theme.color.border, paddingTop: theme.space["5"] }]}
    >
      {NON_AFFILIATION}
    </Text>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  spacer: {
    flex: 1,
  },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
  },
  shieldSkeleton: {
    alignItems: "center",
  },
  reason: {
    flexDirection: "row",
    alignItems: "flex-start",
    borderLeftWidth: 3,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 7,
  },
  reasonText: {
    flex: 1,
  },
  calmRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  calmDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    marginTop: 7,
  },
  calmText: {
    flex: 1,
    lineHeight: 18,
  },
  notAssessedSub: {
    lineHeight: 20,
  },
  disclaimer: {
    borderTopWidth: 1,
  },
});
