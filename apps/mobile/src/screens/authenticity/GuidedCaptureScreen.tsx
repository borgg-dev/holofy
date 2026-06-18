import { useCallback, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

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
import {
  AUTHENTICITY_PLAN,
  SIGNAL_COPY,
  chipOrderFor,
  refuseMessage,
} from "./capturePlan";
import { CAPTURE_DONE_ANNOUNCE, CAPTURE_TITLE, shotAdvanceAnnounce } from "./copy";
import { useGuidedCapture } from "./useGuidedCapture";

type Props = {
  onBack?: () => void;
  /** Fired once every shot is captured — the route runs the screening and shows the verdict. */
  onComplete?: () => void;
};

// Guided authenticity capture — the capture↔ML dependency made visible for anti-counterfeit.
// It walks the authenticity plan one shot at a time: a tight macro for the print pattern, then
// two holo-tilt passes for the foil signature. Per-shot instruction up top, the teal-lock
// frame, the live quality chips (the shot's primary signal first), and a shutter that refuses a
// sub-threshold shot. Quality is mock-driven; the lock/refuse/advance wiring is real. The
// structure intentionally mirrors the pre-grade capture so the system speaks one consistent voice.
export function GuidedCaptureScreen({ onBack, onComplete }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();

  const { shotIndex, signals, locked, firstFailing, capturedCount, total, complete, capture } =
    useGuidedCapture();

  const [toast, setToast] = useState<string | null>(null);
  const [refuseSignal, setRefuseSignal] = useState(0);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasLocked = useRef(false);

  const shot = AUTHENTICITY_PLAN[shotIndex] ?? AUTHENTICITY_PLAN[0]!;

  // One haptic on the searching→locked edge so readiness is felt, not just seen.
  useEffect(() => {
    if (locked && !wasLocked.current) {
      if (!reduceMotion) impactLight();
      setToast(null);
    }
    wasLocked.current = locked;
  }, [locked, reduceMotion]);

  // Once every shot is captured, announce and hand off to the screening.
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
      AccessibilityInfo.announceForAccessibility(shotAdvanceAnnounce(shot.label));
      capture();
      setToast(null);
      return;
    }
    setRefuseSignal((n) => n + 1);
    setToast(refuseMessage(firstFailing));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }, [locked, firstFailing, capture, shot.label]);

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

      <View
        style={[
          styles.topbar,
          { paddingHorizontal: theme.space["5"], paddingTop: insets.top + theme.space["4"] },
        ]}
      >
        <IconButton accessibilityLabel="Back" onPress={onBack}>
          <ChevronLeft color={theme.color.textPrimary} />
        </IconButton>
        <Text variant="label" tone="secondary">
          {CAPTURE_TITLE}
        </Text>
        {/* Spacer balances the back button so the title sits optically centered. */}
        <View style={{ width: theme.tapTarget }} />
      </View>

      {/* Shot instruction — the one thing that makes this shot readable. */}
      <View
        style={[
          styles.brief,
          { paddingHorizontal: theme.space["6"], top: insets.top + theme.space["11"], gap: theme.space["2"] },
        ]}
        accessibilityRole="header"
      >
        <Text variant="overline" tone="lock">
          {`Shot ${capturedCount + 1} of ${total} · ${shot.label}`}
        </Text>
        <Text variant="bodySm" tone="secondary" style={styles.instruction}>
          {shot.instruction}
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
            paddingBottom: insets.bottom + theme.space["7"],
            paddingTop: theme.space["7"],
            gap: theme.space["6"],
          },
        ]}
      >
        <CoachingToast message={toast} />

        <ShotProgress total={total} captured={capturedCount} activeIndex={shotIndex} />

        <View style={[styles.chips, { gap: theme.space["3"] }]} accessibilityRole="summary">
          {chipOrderFor(shot).map((key) => {
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
          label={locked ? "Capture shot" : "Hold steady"}
          onPress={handleShutter}
          refuseSignal={refuseSignal}
        />
      </View>
    </Screen>
  );
}

// The multi-shot progress — a row of pips filled as each shot is captured, the active one
// ringed. Reads as an instrument scale, matching the pre-grade capture's progress.
function ShotProgress({
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
      accessibilityLabel={`${captured} of ${total} shots captured`}
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
