import { StyleSheet, View } from "react-native";

import { useTheme } from "@/theme";

// Placeholder for the live camera feed. P1.4 swaps this for expo-camera's
// <CameraView>; until then it stands in a dim photographed surface with a card,
// so the frame, lock, and chips can be composed and reviewed against a realistic
// ground rather than flat black. Nothing below depends on it being mock.
//
// These two tones are mock *photo content* (a dark table under the card), not
// design-system surfaces — they intentionally aren't tokens and get deleted with
// this file when the real camera lands.
const MOCK_TABLE_DARK = "#07060c";
const MOCK_TABLE_LIT = "#161422";

export function CameraPreview() {
  const theme = useTheme();
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <View style={[StyleSheet.absoluteFill, { backgroundColor: MOCK_TABLE_DARK }]} />
      <View style={[styles.ground, { backgroundColor: MOCK_TABLE_LIT }]} />
      {/* The card the user is pointing at, slightly rotated as if hand-held. */}
      <View
        style={[
          styles.card,
          {
            backgroundColor: theme.color.bgRaised,
            borderRadius: theme.radius.card,
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  ground: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: "60%",
    opacity: 0.9,
  },
  card: {
    position: "absolute",
    alignSelf: "center",
    top: "30%",
    width: "56%",
    aspectRatio: 0.714,
    transform: [{ rotate: "-1.5deg" }],
    opacity: 0.96,
  },
});
