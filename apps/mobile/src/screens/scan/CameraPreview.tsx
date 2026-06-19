import { type RefObject } from "react";
import { StyleSheet, View } from "react-native";

import { CameraView } from "expo-camera";

import { useTheme } from "@/theme";

// The live capture ground. On a real device with camera permission it's expo-camera's
// <CameraView>; otherwise (web/demo, or before permission) it renders a stand-in dim surface
// with a card so the frame, lock, and chips still compose against a realistic ground rather
// than flat black. The two stand-in tones are mock *photo content* (a dark table), not design
// tokens — they intentionally aren't tokens.
const MOCK_TABLE_DARK = "#07060c";
const MOCK_TABLE_LIT = "#161422";

type Props = {
  /** When true, render the real camera feed; the ref drives takePictureAsync. */
  live?: boolean;
  cameraRef?: RefObject<CameraView>;
};

export function CameraPreview({ live = false, cameraRef }: Props) {
  const theme = useTheme();

  if (live) {
    return <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />;
  }

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
