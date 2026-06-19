import type { ExpoConfig } from "expo/config";

// Holofy ships dark-first: the Vault background must be painted before the JS
// bundle mounts, otherwise the first frame flashes white. splash + backgroundColor
// + userInterfaceStyle all pin to the near-black Vault from the design tokens
// (#0B0B12 — kept literal here because app.config is read by native tooling that
// can't import the TS token module).
const VAULT = "#0B0B12";

const config: ExpoConfig = {
  name: "Holofy",
  slug: "holofy",
  scheme: "holofy",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "dark",
  backgroundColor: VAULT,
  icon: "./assets/icon.png",
  splash: {
    image: "./assets/splash.png",
    resizeMode: "contain",
    backgroundColor: VAULT,
  },
  assetBundlePatterns: ["**/*"],
  ios: {
    supportsTablet: false,
    bundleIdentifier: "com.holofy.app",
    infoPlist: {
      NSCameraUsageDescription:
        "Holofy uses the camera to scan your cards so it can value, verify, and pre-grade them.",
    },
  },
  android: {
    package: "com.holofy.app",
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: VAULT,
    },
    permissions: ["CAMERA"],
  },
  plugins: [
    "expo-router",
    "expo-font",
    [
      "expo-camera",
      {
        cameraPermission:
          "Holofy uses the camera to scan your cards so it can value, verify, and pre-grade them.",
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
};

export default config;
