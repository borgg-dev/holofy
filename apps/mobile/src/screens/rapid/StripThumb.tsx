import { useEffect } from "react";
import { StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { Text, ValueText } from "@/components";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { identitySubline } from "../shared/format";
import { PENDING_LABEL, UNREADABLE_LABEL } from "./copy";
import { entryCount, type StripEntry } from "./stack";

type Props = {
  entry: StripEntry;
  /** True for the just-landed entry — runs the once-only slide+settle in. */
  fresh: boolean;
};

// One card in the live filmstrip: a card-ratio thumbnail standing in for the captured
// photo (the user's frame lands here on device), the name, and its € — or a quiet
// "Reading…" / "Missed" state. A merged card wears a count badge (×2). The fresh entry
// slides up and settles once; reduced motion lands it already settled.
export function StripThumb({ entry, fresh }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const enter = useSharedValue(fresh && !reduceMotion ? 0 : 1);
  useEffect(() => {
    if (!fresh || reduceMotion) {
      enter.value = 1;
      return;
    }
    enter.value = withTiming(1, {
      duration: theme.motion.duration.base,
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });
  }, [fresh, reduceMotion, enter, theme.motion.duration.base]);

  const style = useAnimatedStyle(() => ({
    opacity: enter.value,
    transform: [{ translateY: (1 - enter.value) * 14 }],
  }));

  const read = entry.read;
  const count = entryCount(entry);
  const identified = read.kind === "identified";
  const a11y = stripThumbA11y(entry);

  return (
    <Animated.View accessibilityLabel={a11y} style={[styles.col, { width: 116 }, style]}>
      <View
        style={[
          styles.thumb,
          {
            backgroundColor: theme.color.bgInset,
            borderRadius: theme.radius.md,
            borderColor: identified
              ? withAlpha(theme.color.holoViolet, 0.4)
              : withAlpha(theme.color.border, 0.9),
          },
        ]}
      >
        {!identified ? (
          <View style={styles.thumbState}>
            <View
              style={[
                styles.stateDot,
                { backgroundColor: read.kind === "pending" ? theme.color.vaultTeal : theme.color.textTertiary },
              ]}
            />
            <Text variant="caption" tone="tertiary">
              {read.kind === "pending" ? PENDING_LABEL : UNREADABLE_LABEL}
            </Text>
          </View>
        ) : null}
        {count > 1 ? (
          <View
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
            style={[styles.badge, { backgroundColor: theme.color.holoViolet, borderColor: theme.color.bg }]}
          >
            <Text variant="caption" tone="onAccent" tabular style={styles.badgeText}>
              ×{count}
            </Text>
          </View>
        ) : null}
      </View>

      {identified ? (
        <View style={styles.meta}>
          <Text variant="caption" tone="primary" numberOfLines={1}>
            {read.identity.name}
          </Text>
          {read.price?.value != null ? (
            <ValueText amount={read.price.value} usdValue={read.price.usdValue} currency={read.price.currency} variant="body" />
          ) : (
            <Text variant="caption" tone="secondary">
              No € comp
            </Text>
          )}
        </View>
      ) : (
        <View style={styles.meta}>
          <Text variant="caption" tone="tertiary" numberOfLines={1}>
            {read.kind === "pending" ? "Identifying" : "Flip again"}
          </Text>
        </View>
      )}
    </Animated.View>
  );
}

function stripThumbA11y(entry: StripEntry): string {
  const read = entry.read;
  if (read.kind === "pending") return "Reading a card";
  if (read.kind === "unreadable") return "A flip that read no card";
  const count = entryCount(entry);
  const times = count > 1 ? `, ${count} in your stack` : "";
  const priced =
    read.price?.value != null
      ? new Intl.NumberFormat("de-DE", { style: "currency", currency: read.price.currency }).format(
          read.price.value
        )
      : "no recent euro sales";
  return `${read.identity.name}, ${identitySubline(read.identity)}, ${priced}${times}`;
}

const styles = StyleSheet.create({
  col: { gap: 8 },
  thumb: {
    width: "100%",
    aspectRatio: 0.714,
    borderWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  thumbState: { alignItems: "center", gap: 6, paddingHorizontal: 8 },
  stateDot: { width: 7, height: 7, borderRadius: 4 },
  badge: {
    position: "absolute",
    top: 6,
    right: 6,
    minWidth: 24,
    height: 22,
    borderRadius: 11,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  badgeText: { fontWeight: "700" },
  meta: { gap: 2 },
});
