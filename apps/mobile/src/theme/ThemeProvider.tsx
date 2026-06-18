import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibilityInfo, useColorScheme } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { darkTheme, lightTheme, type ColorScheme, type Theme } from "./theme";
import {
  DEFAULT_THEME_MODE,
  THEME_MODE_STORAGE_KEY,
  parseThemeMode,
  resolveScheme,
  type ThemeMode,
} from "./themeMode";

type ThemeContextValue = {
  theme: Theme;
  scheme: ColorScheme;
  /** The user's appearance preference: "system" follows the OS, "light"/"dark" pin it. */
  mode: ThemeMode;
  /** Set and persist the appearance preference; the whole app re-themes immediately. */
  setThemeMode: (mode: ThemeMode) => void;
  /** True when the OS asks for reduced motion; signature animations honor it. */
  reduceMotion: boolean;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

type Props = {
  children: ReactNode;
  /** Force a scheme (tests, previews). Pins the resolved scheme and skips persistence. */
  forceScheme?: ColorScheme;
};

export function ThemeProvider({ children, forceScheme }: Props) {
  const osScheme = useColorScheme();
  const [mode, setMode] = useState<ThemeMode>(DEFAULT_THEME_MODE);

  // Hydrate the saved preference once on mount. The default "system" mode renders first; if a
  // different mode was stored, the app re-themes on this resolve — a brief default is acceptable
  // and avoids blocking first paint on a storage read. Skipped when a scheme is forced.
  useEffect(() => {
    if (forceScheme) return;
    let mounted = true;
    AsyncStorage.getItem(THEME_MODE_STORAGE_KEY)
      .then((stored) => {
        if (mounted) setMode(parseThemeMode(stored));
      })
      .catch(() => {
        // A failed read leaves us on the default mode — never a reason to crash the shell.
      });
    return () => {
      mounted = false;
    };
  }, [forceScheme]);

  const setThemeMode = useCallback((next: ThemeMode) => {
    setMode(next);
    void AsyncStorage.setItem(THEME_MODE_STORAGE_KEY, next).catch(() => {
      // The in-memory change still applies; persistence is best-effort.
    });
  }, []);

  const scheme: ColorScheme = forceScheme ?? resolveScheme(mode, osScheme);

  const [reduceMotion, setReduceMotion] = useState(false);
  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isReduceMotionEnabled().then((on) => {
      if (mounted) setReduceMotion(on);
    });
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduceMotion);
    return () => {
      mounted = false;
      sub.remove();
    };
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme: scheme === "light" ? lightTheme : darkTheme,
      scheme,
      mode,
      setThemeMode,
      reduceMotion,
    }),
    [scheme, mode, setThemeMode, reduceMotion]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  return useThemeContext().theme;
}

export function useReduceMotion(): boolean {
  return useThemeContext().reduceMotion;
}

export function useThemeMode(): { mode: ThemeMode; setThemeMode: (mode: ThemeMode) => void } {
  const { mode, setThemeMode } = useThemeContext();
  return { mode, setThemeMode };
}

function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>.");
  return ctx;
}
