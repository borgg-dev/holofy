import { Pressable, StyleSheet, View } from "react-native";

import { FoilSurface, Text, ValueText } from "@/components";
import type { BatchNeedsConfirmation, ScanChoice } from "@/api";
import { useCurrency } from "@/currency";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { identitySubline, variantLabel } from "../shared/format";
import { confirmHint } from "./copy";

type Props = {
  item: BatchNeedsConfirmation;
  /** The index the user picked for this card (null = undecided — excluded from bulk add). */
  selected: number | null;
  onSelect: (index: number) => void;
};

// A needs_confirmation card in the review. The same trust-over-speed pattern as the single
// confirm screen — two near-identical variants whose € diverge, the delta called out, the
// collector picks — but inlined per-card so the whole stack confirms in one pass. A picked
// variant joins the bulk add; an undecided one is held out (never silently guessed).
export function ConfirmRow({ item, selected, onSelect }: Props) {
  const theme = useTheme();
  const { format } = useCurrency();
  const top2 = item.choices.slice(0, 2);
  const formattedDelta = item.priceDelta != null ? format(item.priceDelta) : null;

  return (
    <FoilSurface level="raised" padded style={[styles.surface, { gap: theme.space["4"] }]}>
      <Text variant="caption" tone="secondary">
        {confirmHint(formattedDelta)}
      </Text>
      <View
        style={{ gap: theme.space["3"] }}
        accessibilityRole="radiogroup"
        accessibilityLabel="Pick the matching variant"
      >
        {top2.map((choice, i) => (
          <ChoiceRow
            key={choice.identity.canonicalId}
            choice={choice}
            selected={selected === i}
            onSelect={() => onSelect(i)}
          />
        ))}
      </View>
    </FoilSurface>
  );
}

function ChoiceRow({
  choice,
  selected,
  onSelect,
}: {
  choice: ScanChoice;
  selected: boolean;
  onSelect: () => void;
}) {
  const theme = useTheme();
  const { identity, price } = choice;
  const a11y = `${identity.name}, ${variantLabel(identity.variant)}, ${
    price?.value != null
      ? new Intl.NumberFormat("de-DE", { style: "currency", currency: price.currency }).format(price.value)
      : "no recent euro sales"
  }`;

  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      accessibilityLabel={a11y}
      onPress={onSelect}
      style={[
        styles.choice,
        {
          borderColor: selected ? theme.color.accent : theme.color.border,
          borderWidth: selected ? 1.5 : StyleSheet.hairlineWidth,
          borderRadius: theme.radius.md,
          backgroundColor: selected ? withAlpha(theme.color.accent, 0.08) : "transparent",
          padding: theme.space["4"],
          gap: theme.space["3"],
        },
      ]}
    >
      <View
        style={[
          styles.radio,
          {
            borderColor: selected ? theme.color.accent : theme.color.borderStrong,
            backgroundColor: selected ? theme.color.accent : "transparent",
          },
        ]}
      >
        {selected ? <View style={[styles.radioDot, { backgroundColor: theme.color.textOnAccent }]} /> : null}
      </View>
      <View style={[styles.choiceText, { gap: 2 }]}>
        <Text variant="bodySm" tone="primary" numberOfLines={1}>
          {variantLabel(identity.variant)} · {identity.setName}
        </Text>
        <Text variant="caption" tone="tertiary" numberOfLines={1}>
          {identitySubline(identity)}
        </Text>
      </View>
      {price?.value != null ? (
        <ValueText amount={price.value} usdValue={price.usdValue} currency={price.currency} variant="titleMd" />
      ) : (
        <Text variant="caption" tone="secondary">
          No € comp
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  surface: {},
  choice: { flexDirection: "row", alignItems: "center" },
  choiceText: { flex: 1 },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  radioDot: { width: 7, height: 7, borderRadius: 4 },
});
