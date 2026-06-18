// Font assets the app loads at boot via expo-font. Files are not committed here
// (they're OFL and fetched at setup — see README "Fonts"); the map names the
// keys that typography.ts references so a missing file fails loudly at load.
export const fontAssets = {
  "ClashDisplay-Semibold": require("../../assets/fonts/ClashDisplay-Semibold.otf"),
  "Manrope-Regular": require("../../assets/fonts/Manrope-Regular.ttf"),
  "Manrope-Medium": require("../../assets/fonts/Manrope-Medium.ttf"),
  "Manrope-SemiBold": require("../../assets/fonts/Manrope-SemiBold.ttf"),
  "Manrope-Bold": require("../../assets/fonts/Manrope-Bold.ttf"),
} as const;
