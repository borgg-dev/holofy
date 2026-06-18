import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet } from "react-native";

import { useReduceMotion, useTheme } from "@/theme";

type Props = {
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  /** Spoken state for the reader — the control itself reads as a switch. */
  accessibilityLabel: string;
};

// A bespoke consent switch — deliberately not the platform <Switch>, whose stock chrome is
// the exact "generic" tell the Vault avoids. Off reads as a calm inset well; on lights the
// brand-violet "lock" hue, the same active cue the scan-frame and shutter use for a
// deliberate, engaged state. The knob eases across; reduced-motion snaps it. 52pt wide.
const TRACK_WIDTH = 52;
const TRACK_HEIGHT = 32;
const KNOB = 24;
const TRAVEL = TRACK_WIDTH - KNOB - 8;

export function ConsentToggle({ value, onChange, disabled = false, accessibilityLabel }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const progress = useRef(new Animated.Value(value ? 1 : 0)).current;

  useEffect(() => {
    if (reduceMotion) {
      progress.setValue(value ? 1 : 0);
      return;
    }
    Animated.timing(progress, {
      toValue: value ? 1 : 0,
      duration: theme.motion.duration.fast,
      useNativeDriver: false,
    }).start();
  }, [value, reduceMotion, progress, theme.motion.duration.fast]);

  const trackColor = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [theme.color.bgInset, theme.color.lock],
  });
  const knobShift = progress.interpolate({ inputRange: [0, 1], outputRange: [0, TRAVEL] });

  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      accessibilityLabel={accessibilityLabel}
      hitSlop={10}
      disabled={disabled}
      onPress={() => onChange(!value)}
      style={[styles.tap, { opacity: disabled ? 0.45 : 1 }]}
    >
      <Animated.View
        style={[
          styles.track,
          {
            backgroundColor: trackColor,
            borderColor: value ? theme.color.lock : theme.color.border,
          },
        ]}
      >
        <Animated.View
          style={[
            styles.knob,
            { backgroundColor: theme.color.textPrimary, transform: [{ translateX: knobShift }] },
          ]}
        />
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tap: { minHeight: 44, justifyContent: "center", alignItems: "center" },
  track: {
    width: TRACK_WIDTH,
    height: TRACK_HEIGHT,
    borderRadius: TRACK_HEIGHT / 2,
    borderWidth: StyleSheet.hairlineWidth,
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  knob: {
    width: KNOB,
    height: KNOB,
    borderRadius: KNOB / 2,
  },
});
