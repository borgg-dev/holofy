import { useCallback, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, StyleSheet, View } from "react-native";
import * as Haptics from "expo-haptics";

import {
  CoachingToast,
  IconButton,
  ModeToggle,
  QualityChip,
  ScanFrame,
  Screen,
  Shutter,
  Text,
  type CaptureMode,
} from "@/components";
import { ChevronLeft, FlashOff } from "@/components/icons";
import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { CameraPreview } from "./CameraPreview";
import {
  LOCK_ANNOUNCE,
  SHUTTER_LOCKED,
  SHUTTER_REST,
  STACK_NOTICE,
  chipFor,
  refuseMessage,
} from "./copy";
import { useMockCaptureQuality, type QualitySignals } from "./useMockCaptureQuality";

type Props = {
  onBack?: () => void;
  onCaptured?: () => void;
};

const CHIP_ORDER: (keyof QualitySignals)[] = ["focus", "glare", "frame"];

// The scan-frame screen (spec: packages/design-tokens/screens/scan-frame.md).
// Full-bleed camera ground, a corner-bracket target that teal-locks when the
// three live signals pass, coaching chips, and a shutter that refuses a bad shot.
// Quality is mock-driven here; the lock/refuse/announce wiring is the real thing.
export function ScanScreen({ onBack, onCaptured }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  const [mode, setMode] = useState<CaptureMode>("scan");
  const { signals, locked, firstFailing, cycle } = useMockCaptureQuality();

  const [toast, setToast] = useState<string | null>(null);
  const [refuseSignal, setRefuseSignal] = useState(0);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasLocked = useRef(false);

  // Fire one haptic + a polite SR announcement on the searching→locked edge.
  useEffect(() => {
    if (locked && !wasLocked.current) {
      if (!reduceMotion) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
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

  const handleShutter = useCallback(() => {
    if (locked) {
      onCaptured?.();
      return;
    }
    // Refuse-to-grade: shake the shutter, surface the specific coaching line.
    setRefuseSignal((n) => n + 1);
    setToast(refuseMessage(firstFailing));
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }, [locked, firstFailing, onCaptured]);

  return (
    <Screen ground="flat" edges={[]}>
      <CameraPreview />
      {/* Edge vignette so attention falls to the frame. */}
      <View pointerEvents="none" style={[styles.vignette, { borderColor: withAlpha(theme.color.bg, 0.55) }]} />

      <TopBar mode={mode} onMode={setMode} onBack={onBack} />

      <View style={styles.frameZone} pointerEvents="none">
        <ScanFrame locked={locked} />
      </View>

      <View style={styles.coach}>
        <CoachingToast message={toast} />

        {mode === "stack" ? (
          <View style={styles.stackNotice}>
            <Text variant="caption" tone="secondary">
              {STACK_NOTICE}
            </Text>
          </View>
        ) : null}

        <View style={styles.chips} accessibilityRole="summary">
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

        {/* Dev affordance to step the mock quality forward; trimmed in P1.4. */}
        <Text
          variant="caption"
          tone="tertiary"
          onPress={cycle}
          accessibilityLabel="Step the demo capture quality"
          style={styles.devHint}
        >
          Demo: tap to advance capture quality
        </Text>
      </View>
    </Screen>
  );
}

function TopBar({
  mode,
  onMode,
  onBack,
}: {
  mode: CaptureMode;
  onMode: (m: CaptureMode) => void;
  onBack?: () => void;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.topbar, { paddingHorizontal: theme.space["5"], paddingTop: theme.space["7"] }]}>
      <IconButton accessibilityLabel="Back" onPress={onBack}>
        <ChevronLeft color={theme.color.textPrimary} />
      </IconButton>
      <ModeToggle value={mode} onChange={onMode} />
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
    borderWidth: 64,
    borderRadius: 64,
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
    paddingHorizontal: 16,
    paddingBottom: 40,
    paddingTop: 24,
    alignItems: "center",
    gap: 20,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  stackNotice: {
    alignItems: "center",
  },
  devHint: {
    marginTop: -8,
  },
});
