// Font assets the app loads at boot via expo-font. The OFL files are vendored in
// assets/fonts/ (Clash Display from Fontshare, Manrope static weights from Google
// Fonts); the map names the keys that typography.ts references.
export const fontAssets = {
  "ClashDisplay-Semibold": require("../../assets/fonts/ClashDisplay-Semibold.otf"),
  "Manrope-Regular": require("../../assets/fonts/Manrope-Regular.ttf"),
  "Manrope-Medium": require("../../assets/fonts/Manrope-Medium.ttf"),
  "Manrope-SemiBold": require("../../assets/fonts/Manrope-SemiBold.ttf"),
  "Manrope-Bold": require("../../assets/fonts/Manrope-Bold.ttf"),
} as const;
