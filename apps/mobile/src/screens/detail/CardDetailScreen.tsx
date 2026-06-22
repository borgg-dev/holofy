import { ScrollView, StyleSheet, View } from "react-native";

import {
  Button,
  FoilCard,
  FoilSurface,
  IconButton,
  Screen,
  Skeleton,
  Text,
  ValueText,
} from "@/components";
import { ChevronLeft } from "@/components/icons";
import type { CollectionItem } from "@/api";
import { useTheme } from "@/theme";
import {
  conditionLabel,
  identityA11yLabel,
  identitySubline,
  trendFromQuote,
} from "../shared/format";
import { TrendPill } from "../shared/TrendPill";
import { ACTION_AUTH, ACTION_GRADE } from "../reveal/copy";

type Props = {
  /** "loading" while the holding is being fetched; "missing" when the id isn't in the Vault. */
  state: "loading" | "missing" | { item: CollectionItem };
  onBack?: () => void;
  onGrade?: () => void;
  onAuthenticity?: () => void;
  /** Remove this holding from the Vault (the route confirms, then deletes and navigates back). */
  onRemove?: () => void;
};

// The card detail screen — a Vault holding opened. The card sits at rest (no reveal sweep:
// this isn't the pull moment, it's the ledger entry), its current € value and 30-day trend
// beneath, then a small reference panel (low · 30-day average · condition) and the two
// wedge actions: pre-grade and authenticity. Both re-enter the guided capture flow against
// this card. Loading and missing are real states, not a blank.
export function CardDetailScreen({ state, onBack, onGrade, onAuthenticity, onRemove }: Props) {
  const theme = useTheme();

  if (state === "loading") return <DetailLoading onBack={onBack} />;
  if (state === "missing") return <DetailMissing onBack={onBack} />;

  const { item } = state;
  const { identity, price } = item;
  const unit = price?.value ?? null;
  const total = unit != null ? Math.round(unit * item.quantity * 100) / 100 : null;
  const trend = trendFromQuote(price);

  return (
    <Screen ground="vault" padded>
      <Header onBack={onBack} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: theme.space["10"], gap: theme.space["6"] }}
      >
        <View style={[styles.hero, { gap: theme.space["5"] }]}>
          <View style={{ gap: theme.space["1"] }}>
            <Text variant="titleMd" tone="primary">
              {identity.name}
            </Text>
            <Text variant="caption" tone="tertiary">
              {identitySubline(identity)}
            </Text>
          </View>
          <FoilCard
            title={identity.name}
            subtitle={identitySubline(identity)}
            imageUrl={identity.imageUrl}
            accessibilityLabel={`Your card: ${identityA11yLabel(identity)}`}
            reveal={false}
          />
        </View>

        <View style={{ gap: theme.space["2"] }}>
          <Text variant="overline" tone="tertiary">
            MARKET VALUE · CARDMARKET
          </Text>
          {total != null ? (
            <>
              <ValueText amount={total} currency={price?.currency ?? "EUR"} variant="displayXl" />
              {trend ? (
                <View style={[styles.trendRow, { gap: theme.space["3"] }]}>
                  <TrendPill trend={trend} />
                  <Text variant="bodySm" tone="tertiary">
                    30-day trend
                  </Text>
                </View>
              ) : null}
            </>
          ) : (
            <>
              <Text variant="titleLg" tone="secondary">
                No recent € sales
              </Text>
              <Text variant="caption" tone="tertiary">
                We'll alert you when one lists.
              </Text>
            </>
          )}
        </View>

        <ReferencePanel item={item} unit={unit} />

        <View style={{ gap: theme.space["3"], marginTop: theme.space["2"] }}>
          <Button
            label={ACTION_GRADE}
            tier="secondary"
            onPress={onGrade}
            accessibilityHint="Opens the guided multi-angle capture to estimate a grade for this card."
          />
          <Button label={ACTION_AUTH} tier="tertiary" onPress={onAuthenticity} />
        </View>

        {onRemove ? (
          <View style={{ marginTop: theme.space["2"] }}>
            <Button
              label="Remove from Vault"
              tier="tertiary"
              onPress={onRemove}
              accessibilityHint="Removes this card from your collection. Asks you to confirm first."
            />
          </View>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

// The factual value reference — the numbers behind the headline. Each cell is present-or-absent
// honestly: a missing comp shows an em dash, never a fabricated figure.
function ReferencePanel({ item, unit }: { item: CollectionItem; unit: number | null }) {
  const theme = useTheme();
  const { price } = item;
  const currency = price?.currency ?? "EUR";

  return (
    <FoilSurface level="elevated" padded>
      <View style={{ gap: theme.space["4"] }}>
        <RefRow label="Current unit price" value={unit} currency={currency} />
        <RefRow label="30-day average" value={price?.avg30 ?? null} currency={currency} />
        <RefRow label="Recent low" value={price?.low ?? null} currency={currency} />
        <View style={[styles.refRow, { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.color.border, paddingTop: theme.space["4"] }]}>
          <Text variant="bodySm" tone="secondary">
            Condition
          </Text>
          <Text variant="bodySm" tone="primary">
            {conditionLabel(item.condition)}
            {item.quantity > 1 ? ` · ×${item.quantity}` : ""}
          </Text>
        </View>
      </View>
    </FoilSurface>
  );
}

function RefRow({
  label,
  value,
  currency,
}: {
  label: string;
  value: number | null;
  currency: string;
}) {
  return (
    <View style={styles.refRow}>
      <Text variant="bodySm" tone="secondary">
        {label}
      </Text>
      {value != null ? (
        <ValueText amount={value} currency={currency} variant="body" />
      ) : (
        <Text variant="bodySm" tone="tertiary" accessibilityLabel="no figure">
          —
        </Text>
      )}
    </View>
  );
}

function Header({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  return (
    <View style={[styles.header, { marginBottom: theme.space["5"] }]}>
      <IconButton accessibilityLabel="Back to Vault" onPress={onBack}>
        <ChevronLeft color={theme.color.textPrimary} />
      </IconButton>
    </View>
  );
}

function DetailLoading({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  return (
    <Screen ground="vault" padded>
      <Header onBack={onBack} />
      <View style={{ alignItems: "center", gap: theme.space["6"], marginTop: theme.space["6"] }}>
        <Skeleton width="64%" height={300} radius={theme.radius.lg} />
        <Skeleton width={200} height={44} radius={theme.radius.sm} />
        <Skeleton width="100%" height={140} radius={theme.radius.lg} />
      </View>
    </Screen>
  );
}

function DetailMissing({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  return (
    <Screen ground="vault" padded>
      <Header onBack={onBack} />
      <View style={[styles.missing, { gap: theme.space["4"] }]}>
        <Text variant="titleLg" tone="primary" style={styles.centered}>
          Card not found
        </Text>
        <Text variant="bodySm" tone="secondary" style={styles.centered}>
          This holding isn't in your Vault anymore.
        </Text>
        <Button label="Back to Vault" tier="secondary" onPress={onBack} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center" },
  hero: { alignItems: "center" },
  trendRow: { flexDirection: "row", alignItems: "center" },
  refRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  missing: { flex: 1, alignItems: "center", justifyContent: "center" },
  centered: { textAlign: "center" },
});
