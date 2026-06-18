import { StyleSheet, View } from "react-native";

import type { AuthenticitySignal } from "@/api";
import { Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { SIGNAL_LABEL, signalA11y, signalRead, type SignalReadTone } from "./band";

type Props = {
  signal: AuthenticitySignal;
};

// One per-signal read: the signal name + its state pill, then the human-facing detail.
// A `consistent` read tints teal; `caution` (inconclusive / doesn't-match) tints amber —
// never red, never "fake". An `unreadable` read is a neutral grey: it widened uncertainty
// rather than counting against the card, so it must not look like a strike. The state word
// always carries the meaning, so color is never the sole signal (a11y).
export function SignalRow({ signal }: Props) {
  const theme = useTheme();
  const read = signalRead(signal);
  const palette = PALETTE(theme)[read.tone];

  return (
    <View
      style={[styles.row, { gap: theme.space["3"] }]}
      accessibilityRole="text"
      accessibilityLabel={signalA11y(signal)}
    >
      <View style={[styles.top, { gap: theme.space["3"] }]}>
        <Text variant="bodySm" tone="primary" style={styles.label}>
          {SIGNAL_LABEL[signal.kind]}
        </Text>
        <View
          style={[styles.pill, { backgroundColor: palette.bg, borderRadius: theme.radius.pill }]}
          accessibilityElementsHidden
          importantForAccessibility="no"
        >
          <Text variant="overline" style={{ color: palette.fg }}>
            {read.state}
          </Text>
        </View>
      </View>
      <Text variant="caption" tone="tertiary" style={styles.detail}>
        {signal.detail}
      </Text>
    </View>
  );
}

// Tone → color, drawn from the theme so nothing is hardcoded. Teal for consistent, amber for
// caution, a muted neutral for an unreadable signal. Red is absent by design (charter §3.5).
function PALETTE(theme: ReturnType<typeof useTheme>): Record<SignalReadTone, { fg: string; bg: string }> {
  return {
    consistent: { fg: theme.color.vaultTeal, bg: withAlpha(theme.color.vaultTeal, 0.14) },
    caution: { fg: theme.color.amber, bg: theme.color.amberSoft },
    unread: { fg: theme.color.textTertiary, bg: theme.color.bgRaised },
  };
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
    flex: 1,
    fontWeight: "600",
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  detail: {
    lineHeight: 18,
  },
});
