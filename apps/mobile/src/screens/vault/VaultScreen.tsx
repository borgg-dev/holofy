import { useCallback, useEffect, useState } from "react";
import { AccessibilityInfo, FlatList, Pressable, StyleSheet, View } from "react-native";

import {
  Button,
  CountUpValue,
  FoilSurface,
  Screen,
  Skeleton,
  Text,
  ValueText,
} from "@/components";
import {
  itemValue,
  portfolioChange,
  useApi,
  type CollectionItem,
  type Portfolio,
  type PortfolioChange,
} from "@/api";
import { ChevronRight } from "@/components/icons";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { conditionLabel, identitySubline } from "../shared/format";
import { TrendPill } from "../shared/TrendPill";

type Props = {
  /** Bumped by the flow on each Add → triggers a refetch so the Vault reflects it. */
  revision?: number;
  /** Start a single guided scan (the Scan tab) — used by the empty state's CTA. */
  onScan?: () => void;
  /** Open the rapid/stack scanner to flip a pile of cards in one pass. */
  onRapidScan?: () => void;
  /** Open a holding's detail screen — its value, history, and pre-grade / authenticity actions. */
  onOpenCard?: (id: string) => void;
};

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; portfolio: Portfolio; items: CollectionItem[] };

// The Vault (portfolio). The collector's net worth in cards: a foil-glowing total that
// counts up, the change since the last snapshot, the holding count, then the list with
// each card's current € contribution. This is a "money" surface — calm, near-black, the
// foil restrained to the total's glow header. Loading / empty / error are all real states.
export function VaultScreen({ revision = 0, onScan, onRapidScan, onOpenCard }: Props) {
  const theme = useTheme();
  const api = useApi();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const [portfolio, items] = await Promise.all([api.portfolio(), api.listCollection()]);
      setState({ status: "ready", portfolio, items });
    } catch {
      setState({ status: "error" });
    }
  }, [api]);

  // Refetch on mount and whenever the flow signals a new add.
  useEffect(() => {
    void load();
  }, [load, revision]);

  if (state.status === "loading") {
    return (
      <Screen ground="vault" edges={["top"]} padded>
        <VaultHeaderSkeleton />
        <View style={{ gap: theme.space["3"], marginTop: theme.space["6"] }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} width="100%" height={72} radius={theme.radius.lg} />
          ))}
        </View>
      </Screen>
    );
  }

  if (state.status === "error") {
    return (
      <Screen ground="vault" edges={["top"]} padded>
        <View style={[styles.centered, { gap: theme.space["4"] }]}>
          <Text variant="titleLg" tone="primary">
            Couldn't load your Vault
          </Text>
          <Text variant="bodySm" tone="secondary" style={styles.centeredText}>
            Check your connection — your collection is safe, this is just the view.
          </Text>
          <Button label="Try again" tier="secondary" onPress={() => void load()} />
        </View>
      </Screen>
    );
  }

  const { portfolio, items } = state;
  const change = portfolioChange(portfolio);
  const empty = items.length === 0;

  return (
    <Screen ground="vault" edges={["top"]} padded>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <VaultHeader
            portfolio={portfolio}
            change={change}
            count={items.reduce((n, it) => n + it.quantity, 0)}
          />
        }
        renderItem={({ item }) => (
          <HoldingRow item={item} onPress={onOpenCard ? () => onOpenCard(item.id) : undefined} />
        )}
        ItemSeparatorComponent={() => <View style={{ height: theme.space["3"] }} />}
        contentContainerStyle={{ paddingBottom: theme.space["10"] }}
        ListEmptyComponent={<EmptyVault onScan={onScan} onRapidScan={onRapidScan} />}
        ListFooterComponent={
          // Scan lives in the tab bar now, so the Vault footer only carries the stack shortcut —
          // the one capture path the bottom bar doesn't already surface.
          empty || !onRapidScan ? null : (
            <View style={{ marginTop: theme.space["7"] }}>
              <Button label="Rapid scan a stack" tier="secondary" onPress={onRapidScan} />
            </View>
          )
        }
      />
    </Screen>
  );
}

function VaultHeader({
  portfolio,
  change,
  count,
}: {
  portfolio: Portfolio;
  change: PortfolioChange | null;
  count: number;
}) {
  const theme = useTheme();

  // Announce the settled total + change once, politely.
  useEffect(() => {
    const total = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
      portfolio.latest.totalValueEur
    );
    const tail = change
      ? `, ${change.direction === "down" ? "down" : "up"} ${new Intl.NumberFormat("de-DE").format(
          Math.abs(change.absolute)
        )} euros since last week`
      : "";
    AccessibilityInfo.announceForAccessibility(`Vault value, ${total}${tail}`);
  }, [portfolio.latest.totalValueEur, change]);

  return (
    <FoilSurface level="elevated" foilEdge padded style={[styles.header, { marginBottom: theme.space["7"] }]}>
      {/* The vault-teal glow that marks this as the value surface. */}
      <View
        pointerEvents="none"
        style={[styles.headerGlow, { backgroundColor: withAlpha(theme.color.vaultTeal, 0.12) }]}
      />
      <Text variant="overline" tone="tertiary">
        VAULT VALUE
      </Text>
      <CountUpValue amount={portfolio.latest.totalValueEur} variant="displayXl" />
      <View style={[styles.headerMeta, { gap: theme.space["3"], marginTop: theme.space["4"] }]}>
        {change && change.fraction != null ? (
          <TrendPill trend={{ fraction: change.fraction, direction: change.direction }} />
        ) : null}
        <Text variant="bodySm" tone="secondary">
          {change ? `${formatSigned(change.absolute)} this week` : "First valuation"} ·{" "}
          {count} {count === 1 ? "card" : "cards"}
        </Text>
      </View>
    </FoilSurface>
  );
}

function HoldingRow({ item, onPress }: { item: CollectionItem; onPress?: () => void }) {
  const theme = useTheme();
  const value = itemValue(item);
  const a11y = `${item.identity.name}, ${conditionLabel(item.condition)}${
    item.quantity > 1 ? `, quantity ${item.quantity}` : ""
  }, ${
    value != null
      ? new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(value)
      : "no recent euro sales"
  }`;

  const inner = (
    <FoilSurface level="raised" padded={false} style={[styles.row, { padding: theme.space["5"] }]}>
      <View style={[styles.rowInner, { gap: theme.space["4"] }]}>
        {/* Card chit — a small near-black tile standing in for the captured thumbnail. */}
        <View
          style={[
            styles.chit,
            { backgroundColor: theme.color.bgInset, borderColor: withAlpha(theme.color.holoViolet, 0.35) },
          ]}
        />
        <View style={[styles.rowText, { gap: theme.space["1"] }]}>
          <Text variant="titleMd" tone="primary" numberOfLines={1}>
            {item.identity.name}
          </Text>
          <Text variant="caption" tone="tertiary" numberOfLines={1}>
            {identitySubline(item.identity)}
          </Text>
          <Text variant="caption" tone="secondary">
            {conditionLabel(item.condition)}
            {item.quantity > 1 ? ` · ×${item.quantity}` : ""}
          </Text>
        </View>
        <View style={[styles.rowValue, { gap: theme.space["2"] }]}>
          {value != null ? (
            <ValueText amount={value} variant="titleMd" />
          ) : (
            <Text variant="bodySm" tone="secondary">
              No € comp
            </Text>
          )}
          {onPress ? <ChevronRight color={theme.color.textTertiary} /> : null}
        </View>
      </View>
    </FoilSurface>
  );

  if (!onPress) {
    return <View accessibilityLabel={a11y}>{inner}</View>;
  }
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={a11y}
      accessibilityHint="Opens this card's detail, value history, and grading actions."
      style={({ pressed }) => ({ opacity: pressed ? 0.75 : 1 })}
    >
      {inner}
    </Pressable>
  );
}

function EmptyVault({ onScan, onRapidScan }: { onScan?: () => void; onRapidScan?: () => void }) {
  const theme = useTheme();
  return (
    <View style={[styles.empty, { gap: theme.space["4"], paddingTop: theme.space["11"] }]}>
      <Text variant="titleLg" tone="primary" style={styles.centeredText}>
        Your Vault is empty
      </Text>
      <Text variant="bodySm" tone="secondary" style={styles.centeredText}>
        Scan your first card to see what your collection is worth.
      </Text>
      <Button label="Scan a card" tier="primary" onPress={onScan} />
      {onRapidScan ? (
        <Button label="Got a stack? Rapid scan" tier="tertiary" onPress={onRapidScan} />
      ) : null}
    </View>
  );
}

function VaultHeaderSkeleton() {
  const theme = useTheme();
  return (
    <FoilSurface level="elevated" foilEdge padded style={styles.header}>
      <Skeleton width={96} height={12} radius={theme.radius.xs} />
      <View style={{ marginTop: theme.space["3"] }}>
        <Skeleton width={220} height={48} radius={theme.radius.sm} />
      </View>
      <View style={{ marginTop: theme.space["4"] }}>
        <Skeleton width={160} height={16} radius={theme.radius.xs} />
      </View>
    </FoilSurface>
  );
}

function formatSigned(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const body = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    Math.abs(value)
  );
  return `${sign}${body}`;
}

const styles = StyleSheet.create({
  header: {
    overflow: "hidden",
  },
  headerGlow: {
    position: "absolute",
    top: -80,
    right: -60,
    width: 220,
    height: 220,
    borderRadius: 220,
  },
  headerMeta: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
  },
  row: {},
  rowInner: { flexDirection: "row", alignItems: "center" },
  // Card chit — a thumbnail-shaped tile (the card aspect at a small fixed size).
  chit: {
    width: 40,
    height: 56,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
  },
  rowText: { flex: 1 },
  rowValue: { alignItems: "flex-end" },
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  centeredText: { textAlign: "center" },
  empty: { alignItems: "center", justifyContent: "center" },
});
