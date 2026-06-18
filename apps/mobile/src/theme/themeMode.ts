import type { ColorScheme } from "./theme";

// The user-facing appearance preference, distinct from the resolved scheme. "system" defers
// to the OS; "light"/"dark" pin the app regardless of it. Default is "system" so a fresh
// install honors the device until the collector chooses otherwise.
export type ThemeMode = "system" | "light" | "dark";

export const THEME_MODES: readonly ThemeMode[] = ["system", "light", "dark"] as const;

// AsyncStorage key for the persisted mode. Namespaced so it never collides with other prefs.
export const THEME_MODE_STORAGE_KEY = "holofy.appearance.mode";

export const DEFAULT_THEME_MODE: ThemeMode = "system";

// Resolve the active scheme from the preference and the OS scheme. Holofy is dark-first, so
// "system" only flips to light on an explicit OS "light"; a null/unknown OS scheme stays dark.
// "light"/"dark" pin the scheme and ignore the OS entirely.
export function resolveScheme(mode: ThemeMode, osScheme: ColorScheme | null | undefined): ColorScheme {
  if (mode === "light") return "light";
  if (mode === "dark") return "dark";
  return osScheme === "light" ? "light" : "dark";
}

// Narrow an unknown persisted value back to a ThemeMode, falling back to the default for any
// legacy/corrupt entry so a bad storage read can never wedge the app on an invalid mode.
export function parseThemeMode(value: string | null | undefined): ThemeMode {
  return value === "system" || value === "light" || value === "dark" ? value : DEFAULT_THEME_MODE;
}
