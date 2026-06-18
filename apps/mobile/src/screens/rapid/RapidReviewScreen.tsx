import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibilityInfo, ScrollView, StyleSheet, View } from "react-native";

import { Button, FoilSurface, Screen, Skeleton, Text } from "@/components";
import type { BatchScan, BatchScanItem } from "@/api";
import { useTheme } from "@/theme";
import { ConfirmRow } from "./ConfirmRow";
import { ResolvedRow } from "./ResolvedRow";
import {
  BULK_ADD_HINT,
  NOTHING_TO_ADD_SUB,
  NOTHING_TO_ADD_TITLE,
  QUOTA_UPGRADE_CTA,
  RECAPTURE_CTA,
  RESOLVED_HINT,
  REVIEW_BACK,
  REVIEW_EYEBROW,
  REVIEW_LOADING,
  REVIEW_TITLE,
  SECTION_CONFIRM,
  SECTION_QUOTA,
  SECTION_RESOLVED,
  SECTION_UNRECOGNIZED,
  SELECT_ALL,
  SELECT_NONE,
  UNRECOGNIZED_HINT,
  bulkAddLabel,
  quotaHint,
  unreadCaption,
} from "./copy";
import {
  groupReview,
  reviewKey,
  selectedAdditions,
  type VaultAddition,
} from "./stack";

type Props = {
  /** The authoritative batch result, or null while POST /scan/batch is in flight. */
  batch: BatchScan | null;
  loading: boolean;
  error: boolean;
  busy?: boolean;
  onBack?: () => void;
  onRetry?: () => void;
  /** Commit the selected cards to the Vault in one go. */
  onBulkAdd?: (additions: VaultAddition[]) => void;
  /** Re-enter the single guided capture to grade / authenticate a resolved card. */
  onGrade?: (canonicalId: string) => void;
  /** Re-enter the single scanner to re-shoot an unrecognized flip. */
  onRecapture?: () => void;
  /** Open the upgrade path for quota-exceeded captures. */
  onUpgrade?: () => void;
};

// Confirm-at-end review (master plan §6). The flipped stack comes back from POST /scan/batch
// as four kinds of result, each rendered for what it is: resolved cards the collector bulk-adds,
// close variants to confirm, flips that missed (re-capture), and captures past the free tier's
// daily wall (shown calmly, with the upgrade rationale). Resolved cards carry the ID+value-only
// boundary on every row — grading/authenticity re-enters the single guided capture.
export function RapidReviewScreen({
  batch,
  loading,
  error,
  busy = false,
  onBack,
  onRetry,
  onBulkAdd,
  onGrade,
  onRecapture,
  onUpgrade,
}: Props) {
  const theme = useTheme();
  const groups = useMemo(() => (batch ? groupReview(batch.items) : null), [batch]);

  // Resolved cards default to selected — the common case is "keep them all".
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [picks, setPicks] = useState<Map<string, number | null>>(new Map());

  useEffect(() => {
    if (!groups) return;
    setSelected(new Set(groups.resolved.map(reviewKey)));
    setPicks(new Map(groups.needsConfirmation.map((it) => [reviewKey(it), null])));
  }, [groups]);

  const additions = useMemo(
    () => (groups ? selectedAdditions(groups, selected, picks) : []),
    [groups, selected, picks]
  );

  if (loading) return <ReviewLoading onBack={onBack} />;
  if (error || !batch || !groups) return <ReviewError onBack={onBack} onRetry={onRetry} />;

  const toggle = (item: BatchScanItem) => {
    const key = reviewKey(item);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const setPick = (item: BatchScanItem, index: number) => {
    setPicks((prev) => new Map(prev).set(reviewKey(item), index));
  };

  const allSelected = groups.resolved.length > 0 && selected.size === groups.resolved.length;
  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(groups.resolved.map(reviewKey)));
  };

  const nothingToAdd =
    groups.resolved.length === 0 && groups.needsConfirmation.length === 0;

  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: theme.space["6"] }}>
        <View style={styles.topbar}>
          <Text
            variant="label"
            tone="secondary"
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Back to flipping the stack"
          >
            {REVIEW_BACK}
          </Text>
        </View>

        <View style={[styles.header, { gap: theme.space["2"], marginTop: theme.space["3"] }]}>
          <Text variant="overline" tone="tertiary">
            {REVIEW_EYEBROW}
          </Text>
          <Text variant="titleLg" tone="primary">
            {REVIEW_TITLE}
          </Text>
        </View>

        {nothingToAdd ? (
          <View style={[styles.nothing, { gap: theme.space["3"], marginTop: theme.space["9"] }]}>
            <Text variant="titleMd" tone="primary" style={styles.center}>
              {NOTHING_TO_ADD_TITLE}
            </Text>
            <Text variant="bodySm" tone="secondary" style={styles.center}>
              {NOTHING_TO_ADD_SUB}
            </Text>
          </View>
        ) : null}

        {groups.resolved.length > 0 ? (
          <Section
            title={SECTION_RESOLVED}
            hint={RESOLVED_HINT}
            trailing={
              <Text
                variant="label"
                tone="accent"
                onPress={toggleAll}
                accessibilityRole="button"
                accessibilityLabel={allSelected ? SELECT_NONE : SELECT_ALL}
              >
                {allSelected ? SELECT_NONE : SELECT_ALL}
              </Text>
            }
          >
            {groups.resolved.map((item) => (
              <ResolvedRow
                key={reviewKey(item)}
                item={item}
                selected={selected.has(reviewKey(item))}
                onToggle={() => toggle(item)}
                onGrade={() => onGrade?.(item.identity.canonicalId)}
              />
            ))}
          </Section>
        ) : null}

        {groups.needsConfirmation.length > 0 ? (
          <Section title={SECTION_CONFIRM}>
            {groups.needsConfirmation.map((item) => (
              <ConfirmRow
                key={reviewKey(item)}
                item={item}
                selected={picks.get(reviewKey(item)) ?? null}
                onSelect={(index) => setPick(item, index)}
              />
            ))}
          </Section>
        ) : null}

        {groups.unrecognized.length > 0 ? (
          <Section title={SECTION_UNRECOGNIZED} hint={UNRECOGNIZED_HINT}>
            <FoilSurface level="inset" padded style={{ gap: theme.space["3"] }}>
              <Text variant="bodySm" tone="secondary">
                {unreadCaption(groups.unrecognized.reduce((n, it) => n + it.count, 0))}
              </Text>
              <Button label={RECAPTURE_CTA} tier="secondary" onPress={onRecapture} />
            </FoilSurface>
          </Section>
        ) : null}

        {groups.quotaExceeded.length > 0 ? (
          <Section title={SECTION_QUOTA}>
            <QuotaCard
              rejected={batch.quota.rejected}
              limit={batch.quota.limit}
              onUpgrade={onUpgrade}
            />
          </Section>
        ) : null}
      </ScrollView>

      {!nothingToAdd ? (
        <View style={[styles.footer, { paddingTop: theme.space["4"], borderTopColor: theme.color.border }]}>
          <Button
            label={bulkAddLabel(additions.length)}
            tier="primary"
            disabled={additions.length === 0}
            busy={busy}
            onPress={() => onBulkAdd?.(additions)}
            accessibilityHint={BULK_ADD_HINT}
          />
        </View>
      ) : null}
    </Screen>
  );
}

function Section({
  title,
  hint,
  trailing,
  children,
}: {
  title: string;
  hint?: string;
  trailing?: ReactNode;
  children: ReactNode;
}) {
  const theme = useTheme();
  return (
    <View style={{ marginTop: theme.space["7"], gap: theme.space["3"] }}>
      <View style={styles.sectionHead}>
        <Text variant="overline" tone="tertiary">
          {title}
        </Text>
        {trailing}
      </View>
      {hint ? (
        <Text variant="caption" tone="secondary" style={{ marginTop: -theme.space["1"] }}>
          {hint}
        </Text>
      ) : null}
      <View style={{ gap: theme.space["3"] }}>{children}</View>
    </View>
  );
}

// The quota-exceeded card — calm, never an error. Amber-toned like the coaching surfaces, it
// states the free-tier limit and the path past it without alarm (master plan §4: free 8/day).
function QuotaCard({
  rejected,
  limit,
  onUpgrade,
}: {
  rejected: number;
  limit: number;
  onUpgrade?: () => void;
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.quota,
        {
          backgroundColor: theme.color.amberSoft,
          borderLeftColor: theme.color.amber,
          borderRadius: theme.radius.lg,
          padding: theme.space["5"],
          gap: theme.space["4"],
        },
      ]}
    >
      <Text variant="bodySm" style={{ color: theme.color.onAmber }}>
        {quotaHint(rejected, limit)}
      </Text>
      {onUpgrade ? <Button label={QUOTA_UPGRADE_CTA} tier="secondary" onPress={onUpgrade} /> : null}
    </View>
  );
}

function ReviewLoading({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={styles.topbar}>
        <Text variant="label" tone="secondary" onPress={onBack} accessibilityRole="button" accessibilityLabel="Back">
          {REVIEW_BACK}
        </Text>
      </View>
      <View style={[styles.header, { gap: theme.space["2"], marginTop: theme.space["3"] }]} accessibilityLabel={REVIEW_LOADING}>
        <Text variant="overline" tone="tertiary">
          {REVIEW_EYEBROW}
        </Text>
        <Text variant="titleLg" tone="primary">
          {REVIEW_LOADING}
        </Text>
      </View>
      <View style={{ gap: theme.space["3"], marginTop: theme.space["7"] }}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} width="100%" height={88} radius={theme.radius.lg} />
        ))}
      </View>
    </Screen>
  );
}

function ReviewError({ onBack, onRetry }: { onBack?: () => void; onRetry?: () => void }) {
  const theme = useTheme();
  useEffect(() => {
    AccessibilityInfo.announceForAccessibility("We couldn't read the stack. Try again.");
  }, []);
  return (
    <Screen ground="vault" edges={["top", "bottom"]} padded>
      <View style={[styles.errorBody, { gap: theme.space["4"] }]}>
        <Text variant="titleLg" tone="primary" style={styles.center}>
          We couldn't read the stack
        </Text>
        <Text variant="bodySm" tone="secondary" style={styles.center}>
          Nothing was added — check your connection and run the stack again.
        </Text>
        <View style={{ gap: theme.space["2"], alignSelf: "stretch" }}>
          <Button label="Try again" tier="primary" onPress={onRetry} />
          <Button label="Back to flipping" tier="tertiary" onPress={onBack} />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topbar: { flexDirection: "row", alignItems: "center" },
  header: {},
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  nothing: { alignItems: "center" },
  center: { textAlign: "center" },
  errorBody: { flex: 1, alignItems: "center", justifyContent: "center" },
  footer: { borderTopWidth: StyleSheet.hairlineWidth },
  quota: { borderLeftWidth: 3, overflow: "hidden" },
});
