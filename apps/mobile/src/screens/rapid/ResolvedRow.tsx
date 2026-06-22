import { Pressable, StyleSheet, View } from "react-native";

import { FoilSurface, Text, ValueText } from "@/components";
import type { BatchResolved } from "@/api";
import { useCurrency } from "@/currency";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { identitySubline } from "../shared/format";
import { GRADE_AFFORDANCE, GRADE_AFFORDANCE_HINT } from "./copy";

type Props = {
  item: BatchResolved;
  selected: boolean;
  onToggle: () => void;
  /** Re-enter the single guided capture to grade / authenticate this card. */
  onGrade: () => void;
};

// A resolved card in the review: a selectable holding row (the checkbox bulk-add uses) with
// its € and, when flipped past more than once, an ×N. The footer carries the deliberate
// boundary — "Grade / Check authenticity" re-enters the *single* guided capture, because you
// can't grade or authenticate from a rapid flip (master plan §7). It's a clear affordance, not
// a missing feature: the chevron and hint say it takes you somewhere more careful.
export function ResolvedRow({ item, selected, onToggle, onGrade }: Props) {
  const theme = useTheme();
  const { format } = useCurrency();
  const value = item.price?.value;
  const totalValue = value != null ? value * item.count : null;
  const a11y = `${item.identity.name}, ${identitySubline(item.identity)}, ${
    totalValue != null ? format(totalValue) : "no recent sales"
  }${item.count > 1 ? `, ${item.count} copies` : ""}`;

  return (
    <FoilSurface
      level="raised"
      foilEdge={selected}
      padded={false}
      style={[
        styles.surface,
        {
          borderColor: selected ? theme.color.accent : theme.color.border,
          borderWidth: selected ? 1.5 : StyleSheet.hairlineWidth,
        },
      ]}
    >
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: selected }}
        accessibilityLabel={a11y}
        onPress={onToggle}
        style={[styles.main, { padding: theme.space["5"], gap: theme.space["4"] }]}
      >
        <View
          style={[
            styles.check,
            {
              borderColor: selected ? theme.color.accent : theme.color.borderStrong,
              backgroundColor: selected ? theme.color.accent : "transparent",
              borderRadius: theme.radius.sm,
            },
          ]}
        >
          {selected ? <View style={[styles.tick, { borderColor: theme.color.textOnAccent }]} /> : null}
        </View>

        <View style={[styles.text, { gap: theme.space["1"] }]}>
          <View style={styles.nameRow}>
            <Text variant="titleMd" tone="primary" numberOfLines={1} style={styles.name}>
              {item.identity.name}
            </Text>
            {item.count > 1 ? (
              <View
                style={[
                  styles.qty,
                  { backgroundColor: withAlpha(theme.color.holoViolet, 0.18), borderRadius: theme.radius.pill },
                ]}
              >
                <Text variant="caption" tabular style={{ color: theme.color.textPrimary }}>
                  ×{item.count}
                </Text>
              </View>
            ) : null}
          </View>
          <Text variant="caption" tone="tertiary" numberOfLines={1}>
            {identitySubline(item.identity)}
          </Text>
        </View>

        <View style={styles.value}>
          {totalValue != null ? (
            <ValueText amount={totalValue} currency={item.price!.currency} variant="titleMd" />
          ) : (
            <Text variant="bodySm" tone="secondary">
              No € comp
            </Text>
          )}
        </View>
      </Pressable>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${GRADE_AFFORDANCE} — ${item.identity.name}`}
        accessibilityHint={GRADE_AFFORDANCE_HINT}
        onPress={onGrade}
        style={({ pressed }) => [
          styles.grade,
          {
            borderTopColor: theme.color.border,
            paddingVertical: theme.space["3"],
            paddingHorizontal: theme.space["5"],
            backgroundColor: pressed ? withAlpha(theme.color.textPrimary, 0.04) : "transparent",
          },
        ]}
      >
        <Text variant="label" tone="accent">
          {GRADE_AFFORDANCE}
        </Text>
        <Text variant="label" tone="accent">
          ›
        </Text>
      </Pressable>
    </FoilSurface>
  );
}

const styles = StyleSheet.create({
  surface: {},
  main: { flexDirection: "row", alignItems: "center" },
  // A 22pt square checkbox — bulk-select geometry, distinct from confirm's round radio.
  check: { width: 22, height: 22, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  tick: {
    width: 10,
    height: 6,
    borderLeftWidth: 2,
    borderBottomWidth: 2,
    transform: [{ rotate: "-45deg" }],
    marginTop: -2,
  },
  text: { flex: 1 },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  name: { flexShrink: 1 },
  qty: { paddingHorizontal: 7, paddingVertical: 1 },
  value: { alignItems: "flex-end" },
  grade: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderTopWidth: StyleSheet.hairlineWidth,
  },
});
