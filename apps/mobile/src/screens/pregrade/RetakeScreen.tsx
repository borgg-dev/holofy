import { useEffect } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";

import type { PregradeRetake } from "@/api";
import { Button, Screen, Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import {
  NON_AFFILIATION,
  RETAKE_ACTION,
  RETAKE_BACK,
  RETAKE_OVERLINE,
  RETAKE_SUB,
  RETAKE_TITLE,
} from "./copy";

// The refuse-to-grade outcome (gauge spec §52, schema's `retake`). The product won't put
// a confident number on a shot it can't read, so instead of a fabricated grade it coaches
// the specific fixes and routes straight back into guided capture. Framed as "one more
// pass", not failure — amber and calm, never red, never blaming the collector.
export function RetakeScreen({
  retake,
  onRescan,
  onBack,
}: {
  retake: PregradeRetake;
  onRescan?: () => void;
  onBack?: () => void;
}) {
  const theme = useTheme();

  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(
      `${RETAKE_TITLE}. ${retake.reasons.join(" ")}`
    );
  }, [retake.reasons]);

  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.root, { paddingTop: theme.space["9"], gap: theme.space["8"] }]}>
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

        <View style={[styles.spacer]} />

        <View style={{ gap: theme.space["3"] }}>
          <Button
            label={RETAKE_ACTION}
            tier="primary"
            onPress={onRescan}
            accessibilityHint="Reopens the guided multi-angle capture so you can fix the shot."
          />
          <Button label={RETAKE_BACK} tier="tertiary" onPress={onBack} />
        </View>

        <Text
          variant="caption"
          tone="tertiary"
          style={[styles.disclaimer, { borderTopColor: theme.color.border, paddingTop: theme.space["5"] }]}
        >
          {NON_AFFILIATION}
        </Text>
      </View>
    </Screen>
  );
}

// Each coaching reason on an amber-ruled row — the same coaching language as the scan
// frame's refuse-to-grade toast, so the system speaks one consistent voice.
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

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  spacer: {
    flex: 1,
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
  disclaimer: {
    borderTopWidth: 1,
  },
});
