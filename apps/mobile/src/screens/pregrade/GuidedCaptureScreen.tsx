import { useCallback, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";

import { impactLight } from "@/lib/haptics";

import {
  CoachingToast,
  IconButton,
  QualityChip,
  ScanFrame,
  Screen,
  Shutter,
  Text,
} from "@/components";
import { ChevronLeft } from "@/components/icons";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { CameraPreview } from "../scan/CameraPreview";
import { CAPTURE_PLAN, SIGNAL_COPY, chipOrderFor, refuseMessage } from "./capturePlan";
import {
  CAPTURE_DONE_ANNOUNCE,
  CAPTURE_TITLE,
  angleAdvanceAnnounce,
} from "./copy";
import { useGuidedCapture } from "./useGuidedCapture";

type Props = {
  onBack?: () => void;
  /** Fired once every angle is captured — the route runs the pre-grade and shows the gauge. */
  onComplete?: () => void;
};

// Guided multi-angle capture — the capture↔ML dependency made visible. Unlike the scan
// frame (one flat shot to recognize a card), grading needs a square-on pass for the
// geometric axes and two raking passes for surface (capturePlan.ts). The screen walks the
// plan one angle at a time: per-angle instruction up top, the teal-lock frame, the live
// quality chips (alignment first — skew is the dominant failure), and a shutter that
// refuses a sub-threshold shot. Quality is mock-driven; the lock/refuse/advance wiring is real.
export function GuidedCaptureScreen({ onBack, onComplete }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const { angleIndex, signals, locked, firstFailing, capturedCount, total, complete, capture } =
    useGuidedCapture();

  const [toast, setToast] = useState<string | null>(null);
  const [refuseSignal, setRefuseSignal] = useState(0);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasLocked = useRef(false);

  const angle = CAPTURE_PLAN[angleIndex] ?? CAPTURE_PLAN[0]!;

  // One haptic on the searching→locked edge so the readiness is felt, not just seen.
  useEffect(() => {
    if (locked && !wasLocked.current) {
      if (!reduceMotion) impactLight();
      setToast(null);
    }
    wasLocked.current = locked;
  }, [locked, reduceMotion]);

  // Once every angle is captured, announce and hand off to the assessment.
  useEffect(() => {
    if (!complete) return;
    AccessibilityInfo.announceForAccessibility(CAPTURE_DONE_ANNOUNCE);
    onComplete?.();
  }, [complete, onComplete]);

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    []
  );

  const handleShutter = useCallback(() => {
    if (locked) {
      const next = CAPTURE_PLAN[angleIndex + 1];
      AccessibilityInfo.announceForAccessibility(angleAdvanceAnnounce(angle.label));
      capture();
      if (next) setToast(null);
      return;
    }
    setRefuseSignal((n) => n + 1);
    setToast(refuseMessage(firstFailing));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }, [locked, firstFailing, capture, angle.label, angleIndex]);

  return (
    <Screen ground="flat" edges={[]}>
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

      <View style={[styles.topbar, { paddingHorizontal: theme.space["5"], paddingTop: theme.space["7"] }]}>
        <IconButton accessibilityLabel="Back" onPress={onBack}>
          <ChevronLeft color={theme.color.textPrimary} />
        </IconButton>
        <Text variant="label" tone="secondary">
          {CAPTURE_TITLE}
        </Text>
        {/* Spacer balances the back button so the title sits optically centered. */}
        <View style={{ width: theme.tapTarget }} />
      </View>

      {/* Angle instruction — the one thing that makes this shot count. */}
      <View
        style={[
          styles.brief,
          { paddingHorizontal: theme.space["6"], top: theme.space["12"], gap: theme.space["2"] },
        ]}
        accessibilityRole="header"
      >
        <Text variant="overline" tone="lock">
          {`Angle ${capturedCount + 1} of ${total} · ${angle.label}`}
        </Text>
        <Text variant="bodySm" tone="secondary" style={styles.instruction}>
          {angle.instruction}
        </Text>
      </View>

      <View style={styles.frameZone} pointerEvents="none">
        <ScanFrame locked={locked} />
      </View>

      <View
        style={[
          styles.coach,
          {
            paddingHorizontal: theme.space["5"],
            paddingBottom: theme.space["9"],
            paddingTop: theme.space["7"],
            gap: theme.space["6"],
          },
        ]}
      >
        <CoachingToast message={toast} />

        <AngleProgress total={total} captured={capturedCount} activeIndex={angleIndex} />

        <View style={[styles.chips, { gap: theme.space["3"] }]} accessibilityRole="summary">
          {chipOrderFor(angle).map((key) => {
            const copy = SIGNAL_COPY[key];
            const state = signals[key];
            return (
              <QualityChip
                key={key}
                signal={copy.signal}
                label={copy.states[state]}
                state={state}
              />
            );
          })}
        </View>

        <Shutter
          locked={locked}
          label={locked ? "Capture angle" : "Hold steady"}
          onPress={handleShutter}
          refuseSignal={refuseSignal}
        />
      </View>
    </Screen>
  );
}

// The multi-angle progress — a row of pips, filled as each angle is captured, with the
// active one ringed. Reads as an instrument scale, not a generic dotted carousel.
function AngleProgress({
  total,
  captured,
  activeIndex,
}: {
  total: number;
  captured: number;
  activeIndex: number;
}) {
  const theme = useTheme();
  return (
    <View
      style={[styles.progress, { gap: theme.space["3"] }]}
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: captured }}
      accessibilityLabel={`${captured} of ${total} angles captured`}
    >
      {Array.from({ length: total }).map((_, i) => {
        const done = i < captured;
        const active = i === activeIndex && !done;
        return (
          <View
            key={i}
            style={[
              styles.pip,
              {
                backgroundColor: done ? theme.color.lock : withAlpha(theme.color.textPrimary, 0.18),
                borderColor: theme.color.lock,
                borderWidth: active ? 1.5 : 0,
                opacity: done || active ? 1 : 0.7,
              },
            ]}
          />
        );
      })}
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
    justifyContent: "space-between",
  },
  vignette: {
    ...StyleSheet.absoluteFillObject,
  },
  brief: {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 3,
    alignItems: "center",
  },
  instruction: {
    textAlign: "center",
  },
  frameZone: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: "32%",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },
  coach: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 3,
    alignItems: "center",
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
  },
  progress: {
    flexDirection: "row",
    alignItems: "center",
  },
  pip: {
    width: 9,
    height: 9,
    borderRadius: 5,
  },
});
