import { useCallback, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { impactLight, impactMedium, notifyWarning } from "@/lib/haptics";

import { Button, IconButton, ScanFrame, Screen, Text } from "@/components";
import { ChevronLeft } from "@/components/icons";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { CameraPreview } from "../scan/CameraPreview";
import { Filmstrip } from "./Filmstrip";
import {
  CAPTURE_CTA_DONE,
  CAPTURE_CTA_REST,
  MISS_ANNOUNCE,
  RAPID_EYEBROW,
  RAPID_SUBTITLE,
  RAPID_TITLE,
  REVIEW_CTA,
  addedAnnounce,
  mergedAnnounce,
  totalAnnounce,
} from "./copy";
import { applyCapture, entryCount, stripTotals, type StripEntry } from "./stack";
import { useMockStackCaptures } from "./useMockStackCaptures";

type Props = {
  onBack?: () => void;
  /** Hand the flipped capture refs to the review step (which runs POST /scan/batch). */
  onReview?: (captureRefs: string[]) => void;
};

// Rapid stack scanner (master plan §6). Unlike the single guided frame, this stays open and
// tactile: each "Capture card" flip drops onto the live filmstrip with a haptic tick, the
// same card flipped twice merges (its count badge ticks up) instead of doubling, and the
// running count + € total climb in real time. It is ID + value only — stated up front and
// reinforced at review — so nobody expects a grade from a flip. Capture is mock here, the
// strip/merge/announce wiring is the real thing.
export function RapidScanScreen({ onBack, onReview }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const captures = useMockStackCaptures();

  const [strip, setStrip] = useState<StripEntry[]>([]);
  const [freshId, setFreshId] = useState<string | null>(null);
  // Debounce the running-total announce so a quick burst of flips speaks once, not per flip.
  const announceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (announceTimer.current) clearTimeout(announceTimer.current);
    },
    []
  );

  const announceTotalSoon = useCallback((next: StripEntry[]) => {
    if (announceTimer.current) clearTimeout(announceTimer.current);
    announceTimer.current = setTimeout(() => {
      const t = stripTotals(next);
      if (t.cardCount === 0) return;
      const formatted = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
        t.totalEur
      );
      AccessibilityInfo.announceForAccessibility(totalAnnounce(formatted, t.cardCount));
    }, 900);
  }, []);

  const onCapture = useCallback(() => {
    const flip = captures.next();
    if (!flip) return;

    const applied = applyCapture(strip, flip.captureRef, flip.read);
    setStrip(applied.strip);
    setFreshId(applied.entry.id);

    // A haptic that fits the outcome: a crisp tick for a new card, a softer one for a merge
    // (you felt it land *again*), a light warning for a miss.
    if (!reduceMotion) {
      if (applied.entry.read.kind === "unreadable") {
        notifyWarning();
      } else if (applied.effect === "merged") {
        impactLight();
      } else {
        impactMedium();
      }
    }

    // Announce the specific change for SR users — added / merged / missed.
    const read = applied.entry.read;
    if (read.kind === "identified") {
      if (applied.effect === "merged") {
        AccessibilityInfo.announceForAccessibility(
          mergedAnnounce(read.identity.name, entryCount(applied.entry))
        );
      } else {
        const formatted =
          read.price?.value != null
            ? new Intl.NumberFormat("de-DE", { style: "currency", currency: read.price.currency }).format(
                read.price.value
              )
            : null;
        AccessibilityInfo.announceForAccessibility(addedAnnounce(read.identity.name, formatted));
      }
    } else if (read.kind === "unreadable") {
      AccessibilityInfo.announceForAccessibility(MISS_ANNOUNCE);
    }

    announceTotalSoon(applied.strip);
  }, [captures, strip, reduceMotion, announceTotalSoon]);

  const hasCaptured = strip.length > 0;
  const allFlipped = captures.done;

  return (
    <Screen ground="flat" edges={[]} padded={false}>
      <CameraPreview />
      <View
        pointerEvents="none"
        style={[
          styles.vignette,
          {
            borderColor: withAlpha(theme.color.bg, 0.55),
            borderWidth: theme.space["11"],
            borderRadius: theme.space["11"],
          },
        ]}
      />

      <TopBar onBack={onBack} />

      <View style={styles.frameZone} pointerEvents="none">
        <ScanFrame locked />
      </View>

      {/* Intent line over the frame — the value-only promise, set before the first flip. */}
      <View style={[styles.intent, { top: insets.top + theme.space["11"], paddingHorizontal: theme.space["6"] }]}>
        <Text variant="overline" tone="tertiary" style={styles.center}>
          {RAPID_EYEBROW}
        </Text>
        <Text variant="titleMd" tone="primary" style={styles.center}>
          {RAPID_TITLE}
        </Text>
        <Text variant="caption" tone="secondary" style={styles.center}>
          {RAPID_SUBTITLE}
        </Text>
      </View>

      <View
        style={[
          styles.dock,
          {
            backgroundColor: withAlpha(theme.color.bg, 0.92),
            borderTopColor: theme.color.border,
            paddingHorizontal: theme.space["5"],
            paddingTop: theme.space["5"],
            paddingBottom: insets.bottom + theme.space["5"],
            gap: theme.space["5"],
          },
        ]}
      >
        <Filmstrip strip={strip} freshId={freshId} />

        <View style={[styles.actions, { gap: theme.space["3"] }]}>
          <Button
            label={allFlipped ? CAPTURE_CTA_DONE : CAPTURE_CTA_REST}
            tier={hasCaptured ? "secondary" : "primary"}
            onPress={onCapture}
            disabled={allFlipped}
            accessibilityHint="Reads the card in frame and adds it to your stack."
          />
          {hasCaptured ? (
            <Button
              label={REVIEW_CTA}
              tier={allFlipped ? "primary" : "tertiary"}
              onPress={() => onReview?.(strip.flatMap((e) => e.captureRefs))}
              accessibilityHint="Stops flipping and reviews the stack before adding to your Vault."
            />
          ) : null}
        </View>
      </View>
    </Screen>
  );
}

function TopBar({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.topbar,
        { paddingHorizontal: theme.space["5"], paddingTop: insets.top + theme.space["4"] },
      ]}
    >
      <IconButton accessibilityLabel="Back" onPress={onBack}>
        <ChevronLeft color={theme.color.textPrimary} />
      </IconButton>
    </View>
  );
}

const styles = StyleSheet.create({
  topbar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 3,
    flexDirection: "row",
    alignItems: "center",
  },
  vignette: { ...StyleSheet.absoluteFillObject },
  frameZone: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    // Sit the target higher than the single scanner — the dock owns the lower half.
    bottom: "44%",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },
  intent: {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 3,
    alignItems: "center",
    gap: 4,
  },
  center: { textAlign: "center" },
  dock: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 3,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  actions: {},
});
