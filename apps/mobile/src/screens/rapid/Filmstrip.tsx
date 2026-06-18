import { useEffect, useRef } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { Text, ValueText } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { runningCount, STRIP_EMPTY } from "./copy";
import { StripThumb } from "./StripThumb";
import { stripTotals, type StripEntry } from "./stack";

type Props = {
  strip: StripEntry[];
  /** The id of the row that changed on the last flip — only that one runs the entrance. */
  freshId: string | null;
};

// The live results filmstrip at the foot of the rapid scanner: a running count + € total
// header, then a horizontal track of captured cards that auto-scrolls to the newest flip.
// Empty, it carries the one-line instruction; the moment a card lands it becomes the strip.
// The € total updates instantly per flip (tabular, no count-up) — a running ticker that climbs
// as you go, not a reveal; the count-up is reserved for the settled reveal/Vault moments.
export function Filmstrip({ strip, freshId }: Props) {
  const theme = useTheme();
  const scroller = useRef<ScrollView>(null);
  const totals = stripTotals(strip);
  const empty = strip.length === 0;

  // Keep the newest flip in view as the track grows.
  useEffect(() => {
    if (!empty) scroller.current?.scrollToEnd({ animated: true });
  }, [strip.length, empty]);

  return (
    <View style={[styles.wrap, { gap: theme.space["4"] }]}>
      <View style={[styles.header, { paddingHorizontal: theme.space["1"] }]}>
        <View style={{ gap: 2 }}>
          <Text variant="overline" tone="tertiary">
            STACK TOTAL
          </Text>
          <View style={styles.totalRow}>
            <ValueText amount={totals.totalEur} variant="titleLg" />
            {totals.unpricedCount > 0 ? (
              <Text variant="caption" tone="tertiary">
                +{totals.unpricedCount} no comp
              </Text>
            ) : null}
          </View>
        </View>
        <View
          style={[
            styles.countPill,
            {
              backgroundColor: withAlpha(theme.color.vaultTeal, 0.14),
              borderRadius: theme.radius.pill,
              paddingHorizontal: theme.space["3"],
              paddingVertical: theme.space["1"],
            },
          ]}
        >
          <Text variant="label" tabular style={{ color: theme.color.vaultTeal }}>
            {runningCount(totals.cardCount)}
          </Text>
        </View>
      </View>

      {empty ? (
        <View
          style={[
            styles.emptyTrack,
            { borderColor: theme.color.border, borderRadius: theme.radius.lg },
          ]}
        >
          <Text variant="bodySm" tone="tertiary" style={styles.emptyText}>
            {STRIP_EMPTY}
          </Text>
        </View>
      ) : (
        <ScrollView
          ref={scroller}
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={[styles.track, { gap: theme.space["3"] }]}
        >
          {strip.map((entry) => (
            <StripThumb key={entry.id} entry={entry} fresh={entry.id === freshId} />
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {},
  header: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },
  totalRow: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  countPill: { alignSelf: "flex-end" },
  track: { paddingHorizontal: 2, paddingBottom: 2 },
  emptyTrack: {
    height: 168,
    borderWidth: StyleSheet.hairlineWidth,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  emptyText: { textAlign: "center" },
});
