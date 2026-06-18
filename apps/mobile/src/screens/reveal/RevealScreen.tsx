import { useEffect, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";

import { Button, CountUpValue, FoilCard, Screen, Skeleton, Text } from "@/components";
import type { CardIdentity, PriceQuote } from "@/api";
import { useReduceMotion, useTheme } from "@/theme";
import {
  formatTrendPercent,
  identityA11yLabel,
  identitySubline,
  trendA11y,
  trendFromQuote,
} from "../shared/format";
import { TrendPill } from "../shared/TrendPill";
import {
  ACTION_ADD,
  ACTION_ADDED,
  ACTION_AUTH,
  ACTION_GRADE,
  ADD_HINT,
  EYEBROW_FETCHING,
  EYEBROW_NO_PRICE,
  EYEBROW_PRICE,
  GRADE_HINT,
  NO_PRICE_SUB,
  NO_PRICE_TITLE,
  trendLine,
  valueAnnounce,
} from "./copy";

type Props = {
  identity: CardIdentity;
  /** The resolved price, or null for a recognized-but-no-comp card. */
  price: PriceQuote | null;
  /** Card recognized but the € value is still arriving — value block is a skeleton. */
  pricing?: boolean;
  added?: boolean;
  busy?: boolean;
  onAdd?: () => void;
  onGrade?: () => void;
  onAuthenticity?: () => void;
  onBack?: () => void;
};

// The Foil reveal (foil-reveal.md) — the payoff. The card lifts off the Vault with a
// once-only foil sweep (FoilCard), the € value counts up in tabular figures, and the
// factual identity + 30-day trend settle in beneath. Actions are disabled until the
// reveal settles (~900ms) so nobody taps mid-animation. Reduced motion renders the
// settled state instantly with the final value. The composition is intentionally not
// centered-everything: the value block and identity are left-aligned beneath the hero.
export function RevealScreen({
  identity,
  price,
  pricing = false,
  added = false,
  busy = false,
  onAdd,
  onGrade,
  onAuthenticity,
  onBack,
}: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  // Gate actions until the reveal settles so a tap never lands mid-sweep.
  const [settled, setSettled] = useState(reduceMotion);
  useEffect(() => {
    if (reduceMotion) {
      setSettled(true);
      return;
    }
    const t = setTimeout(() => setSettled(true), theme.motion.duration.reveal);
    return () => clearTimeout(t);
  }, [reduceMotion, theme.motion.duration.reveal]);

  const trend = trendFromQuote(price);
  const hasPrice = !pricing && price?.value != null;

  // Announce the settled value once, politely — SR users never wait on the count-up.
  useEffect(() => {
    if (!settled || !hasPrice || price?.value == null) return;
    const formatted = new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: price.currency,
    }).format(price.value);
    const trendFragment = trend ? trendA11y(trend) : null;
    AccessibilityInfo.announceForAccessibility(valueAnnounce(formatted, trendFragment));
  }, [settled, hasPrice, price, trend]);

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
          ‹ Scan another
        </Text>
      </View>

      <View style={[styles.hero, { gap: theme.space["5"] }]}>
        {/* Identity above the card (titleMd name + caption sub-line). */}
        <View style={[styles.identity, { gap: theme.space["1"] }]}>
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
          accessibilityLabel={`Your scanned card: ${identityA11yLabel(identity)}`}
          reveal
        />
      </View>

      {/* Value block — left-aligned beneath the card. */}
      <View style={[styles.valueBlock, { gap: theme.space["2"] }]}>
        {pricing ? (
          <PricingState />
        ) : hasPrice && price?.value != null ? (
          <>
            <Text variant="overline" tone="tertiary">
              {EYEBROW_PRICE}
            </Text>
            <View style={styles.valueRow}>
              <CountUpValue amount={price.value} currency={price.currency} variant="displayXl" />
            </View>
            {trend ? (
              <View style={[styles.trendRow, { gap: theme.space["3"] }]}>
                <TrendPill trend={trend} />
                <Text variant="bodySm" tone="tertiary">
                  {trendLine(formatTrendPercent(trend.fraction))}
                </Text>
              </View>
            ) : null}
          </>
        ) : (
          <NoPriceState />
        )}
      </View>

      {/* Actions — primary Add, secondary Pre-grade, tertiary Check authenticity. */}
      <View style={[styles.actions, { gap: theme.space["3"], marginTop: theme.space["7"] }]}>
        <Button
          label={added ? ACTION_ADDED : ACTION_ADD}
          tier="primary"
          onPress={onAdd}
          disabled={!settled || added}
          busy={busy}
          accessibilityHint={ADD_HINT}
        />
        <Button
          label={ACTION_GRADE}
          tier="secondary"
          onPress={onGrade}
          disabled={!settled}
          accessibilityHint={GRADE_HINT}
        />
        <Button label={ACTION_AUTH} tier="tertiary" onPress={onAuthenticity} disabled={!settled} />
      </View>
    </Screen>
  );
}

// Card recognized, € value still arriving — eyebrow tells the truth, value is a skeleton.
function PricingState() {
  const theme = useTheme();
  return (
    <View accessibilityLabel="Fetching the Cardmarket price">
      <Text variant="overline" tone="tertiary">
        {EYEBROW_FETCHING}
      </Text>
      <View style={{ marginTop: theme.space["2"] }}>
        <Skeleton width={196} height={44} radius={theme.radius.sm} />
      </View>
      <View style={{ marginTop: theme.space["3"] }}>
        <Skeleton width={148} height={16} radius={theme.radius.xs} />
      </View>
    </View>
  );
}

// Recognized but no liquid € comp — never a fabricated number.
function NoPriceState() {
  return (
    <View>
      <Text variant="overline" tone="tertiary">
        {EYEBROW_NO_PRICE}
      </Text>
      <Text variant="titleLg" tone="secondary">
        {NO_PRICE_TITLE}
      </Text>
      <Text variant="caption" tone="tertiary">
        {NO_PRICE_SUB}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  topbar: {
    flexDirection: "row",
    alignItems: "center",
  },
  hero: {
    flex: 1,
    justifyContent: "center",
  },
  identity: {
    alignSelf: "stretch",
  },
  valueBlock: {
    alignSelf: "stretch",
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "flex-end",
  },
  trendRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  actions: {
    alignSelf: "stretch",
  },
});
