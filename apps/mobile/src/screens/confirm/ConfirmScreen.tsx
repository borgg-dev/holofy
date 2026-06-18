import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { Button, FoilSurface, Screen, Text, ValueText } from "@/components";
import type { ScanChoice } from "@/api";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { identitySubline, variantLabel } from "../shared/format";

type Props = {
  choices: ScanChoice[];
  /** Absolute € gap between the two priced choices — the reason we're asking. */
  priceDelta: number | null;
  busy?: boolean;
  onConfirm?: (choice: ScanChoice) => void;
  onBack?: () => void;
};

// Low-confidence disambiguation (foil-reveal.md "Low-confidence variant"; master plan §5
// — never silently guess). Recognition narrowed it to two near-identical variants whose
// € values diverge sharply; the collector picks. Each candidate shows its own price and
// the delta is called out up top, because *that gap* is why the choice matters. Trust over
// speed — Confirm is required before anything is added to the Vault.
export function ConfirmScreen({ choices, priceDelta, busy = false, onConfirm, onBack }: Props) {
  const theme = useTheme();
  const top2 = choices.slice(0, 2);
  const [selected, setSelected] = useState<number | null>(null);

  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={styles.topbar}>
        <Text
          variant="label"
          tone="secondary"
          onPress={onBack}
          accessibilityRole="button"
          accessibilityLabel="Back to scanner"
        >
          ‹ Scan again
        </Text>
      </View>

      <View style={[styles.header, { gap: theme.space["2"], marginTop: theme.space["3"] }]}>
        <Text variant="overline" tone="tertiary">
          CONFIRM THE VARIANT
        </Text>
        <Text variant="titleLg" tone="primary">
          Two close matches
        </Text>
        <Text variant="bodySm" tone="secondary">
          {priceDelta != null
            ? `These two differ by ${formatDelta(priceDelta)} in value, so we won't guess. Which one is in your hand?`
            : "We found two close matches and won't guess. Which one is in your hand?"}
        </Text>
      </View>

      <View
        style={[styles.choices, { gap: theme.space["4"] }]}
        accessibilityRole="radiogroup"
        accessibilityLabel="Choose the matching variant"
      >
        {top2.map((choice, i) => (
          <ChoiceRow
            key={choice.identity.canonicalId}
            choice={choice}
            selected={selected === i}
            onSelect={() => setSelected(i)}
          />
        ))}
      </View>

      <View style={[styles.actions, { gap: theme.space["4"] }]}>
        <Button
          label="Confirm variant"
          tier="primary"
          disabled={selected == null}
          busy={busy}
          onPress={() => {
            if (selected != null && top2[selected]) onConfirm?.(top2[selected]!);
          }}
          accessibilityHint="Identifies the card and continues to its value."
        />
        <Text variant="caption" tone="tertiary" style={styles.reassure}>
          Neither matches? Scan again with a cleaner shot.
        </Text>
      </View>
    </Screen>
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
    >
      <FoilSurface
        level="raised"
        foilEdge={selected}
        padded={false}
        style={[
          styles.choiceSurface,
          {
            padding: theme.space["5"],
            borderColor: selected ? theme.color.accent : theme.color.border,
            borderWidth: selected ? 1.5 : StyleSheet.hairlineWidth,
          },
        ]}
      >
        <View style={styles.choiceRow}>
          <View style={[styles.choiceText, { gap: theme.space["1"], paddingRight: theme.space["4"] }]}>
            <Text variant="titleMd" tone="primary">
              {identity.name}
            </Text>
            <Text variant="caption" tone="tertiary">
              {identitySubline(identity)}
            </Text>
          </View>
          <View style={styles.choicePrice}>
            {price?.value != null ? (
              <ValueText amount={price.value} currency={price.currency} variant="titleLg" />
            ) : (
              <Text variant="bodySm" tone="secondary">
                No € comp
              </Text>
            )}
            <View
              style={[
                styles.radio,
                {
                  borderColor: selected ? theme.color.accent : theme.color.borderStrong,
                  backgroundColor: selected ? theme.color.accent : "transparent",
                },
              ]}
            >
              {selected ? (
                <View style={[styles.radioDot, { backgroundColor: theme.color.textOnAccent }]} />
              ) : null}
            </View>
          </View>
        </View>
      </FoilSurface>
    </Pressable>
  );
}

function formatDelta(delta: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(delta);
}

const styles = StyleSheet.create({
  topbar: { flexDirection: "row", alignItems: "center" },
  header: {},
  choices: { flex: 1, justifyContent: "center" },
  choiceSurface: {},
  choiceRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  choiceText: { flex: 1 },
  // The price→radio stack: a fixed 10px gap reads tighter than the space scale's 12, by design.
  choicePrice: { alignItems: "flex-end", gap: 10 },
  // Bespoke control geometry (a 22pt radio), not layout spacing — kept as component constants.
  radio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  radioDot: { width: 8, height: 8, borderRadius: 4 },
  actions: {},
  reassure: { textAlign: "center" },
});
