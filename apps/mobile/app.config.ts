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
  owner: "holofy-dev",
  scheme: "holofy",
  version: "0.1.0",
  orientation: "portrait",
  userInterfaceStyle: "dark",
  backgroundColor: VAULT,
  // Use JavaScriptCore, not Hermes, for now. SDK 54's bundled Hermes AOT compiler (hermesc)
  // rejects the modern `#private` class syntax that reanimated v4 ships ("private properties
  // are not supported"), which breaks the release bundle. JSC runs that syntax natively, so
  // the APK builds and runs. Revisit Hermes once the toolchain lowers those fields.
  jsEngine: "jsc",
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
  extra: {
    eas: {
      projectId: "cce0cf1b-4456-4987-b610-9d37f5222380",
    },
  },
};

export default config;
