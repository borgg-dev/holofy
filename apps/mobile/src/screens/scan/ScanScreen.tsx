import { useCallback, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { impactMedium } from "@/lib/haptics";

import {
  CoachingToast,
  IconButton,
  ModeToggle,
  QualityChip,
  ScanFrame,
  Screen,
  Shutter,
  type CaptureMode,
} from "@/components";
import { ChevronLeft, FlashOff } from "@/components/icons";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import type { CaptureImage } from "@/api";

import { CameraPreview } from "./CameraPreview";
import { LOCK_ANNOUNCE, SHUTTER_LOCKED, SHUTTER_REST, chipFor, refuseMessage } from "./copy";
import { useCardCapture } from "./useCardCapture";
import { useMockCaptureQuality, type QualitySignals } from "./useMockCaptureQuality";

type Props = {
  onBack?: () => void;
  /** Receives the captured still to upload + scan. */
  onCaptured?: (image: CaptureImage) => void | Promise<void>;
  /** Selecting Stack mode leaves the single frame for the rapid/stack scanner. */
  onStackMode?: () => void;
};

const CHIP_ORDER: (keyof QualitySignals)[] = ["focus", "glare", "frame"];

// The scan-frame screen (spec: packages/design-tokens/screens/scan-frame.md).
// Full-bleed camera ground, a corner-bracket target that violet-locks (the brand
// capture hue) when the three live signals pass, coaching chips, and a shutter that
// refuses a bad shot.
// Quality is mock-driven here; the lock/refuse/announce wiring is the real thing.
export function ScanScreen({ onBack, onCaptured, onStackMode }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();

  // Selecting Stack hands off to the rapid scanner (a different screen with a different
  // promise); this frame stays the single guided one. Without a handoff the toggle is inert.
  const onMode = useCallback(
    (next: CaptureMode) => {
      if (next === "stack") onStackMode?.();
    },
    [onStackMode]
  );
  const { signals, locked, firstFailing } = useMockCaptureQuality();
  const { cameraRef, permission, requestPermission, capture, live } = useCardCapture();

  // Ask once on mount; on web/denied the preview falls back to the stand-in ground.
  useEffect(() => {
    if (permission && !permission.granted && permission.canAskAgain) requestPermission();
  }, [permission, requestPermission]);

  const [toast, setToast] = useState<string | null>(null);
  const [refuseSignal, setRefuseSignal] = useState(0);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasLocked = useRef(false);

  // Fire one haptic + a polite SR announcement on the searching→locked edge.
  useEffect(() => {
    if (locked && !wasLocked.current) {
      if (!reduceMotion) impactMedium();
      AccessibilityInfo.announceForAccessibility(LOCK_ANNOUNCE);
      setToast(null);
    }
    wasLocked.current = locked;
  }, [locked, reduceMotion]);

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    []
  );

  const handleShutter = useCallback(async () => {
    if (locked) {
      const image = await capture();
      await onCaptured?.(image);
      return;
    }
    // Refuse-to-grade: shake the shutter, surface the specific coaching line.
    setRefuseSignal((n) => n + 1);
    setToast(refuseMessage(firstFailing));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }, [locked, firstFailing, onCaptured, capture]);

  return (
    <Screen ground="flat" edges={[]} padded={false}>
      <CameraPreview live={live} cameraRef={cameraRef} />
      {/* Edge vignette so attention falls to the frame. */}
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

      <TopBar onMode={onMode} onBack={onBack} />

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

        <View style={[styles.chips, { gap: theme.space["3"] }]} accessibilityRole="summary">
          {CHIP_ORDER.map((key) => {
            const { signal, label } = chipFor(key, signals[key]);
            return <QualityChip key={key} signal={signal} label={label} state={signals[key]} />;
          })}
        </View>

        <Shutter
          locked={locked}
          label={locked ? SHUTTER_LOCKED : SHUTTER_REST}
          onPress={handleShutter}
          refuseSignal={refuseSignal}
        />
      </View>
    </Screen>
  );
}

function TopBar({ onMode, onBack }: { onMode: (m: CaptureMode) => void; onBack?: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.topbar,
        { paddingHorizontal: theme.space["5"], paddingTop: insets.top + theme.space["4"] },
      ]}
    >
      {/* As a tab root there's nowhere to go back to, so the chevron only shows when a
          handler is wired (e.g. a deep stack push) — a spacer keeps the toggle centered. */}
      {onBack ? (
        <IconButton accessibilityLabel="Back" onPress={onBack}>
          <ChevronLeft color={theme.color.textPrimary} />
        </IconButton>
      ) : (
        <View style={{ width: theme.tapTarget }} />
      )}
      {/* Stack selects the rapid scanner; this frame stays "scan". */}
      <ModeToggle value="scan" onChange={onMode} />
      <IconButton accessibilityLabel="Flash off">
        <FlashOff color={theme.color.textPrimary} />
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
    justifyContent: "space-between",
  },
  vignette: {
    ...StyleSheet.absoluteFillObject,
  },
  frameZone: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    // Sit the target slightly above optical center (~46%) so chips don't crowd it.
    bottom: "30%",
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
});
