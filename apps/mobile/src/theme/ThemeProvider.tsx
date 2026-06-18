import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibilityInfo, useColorScheme } from "react-native";

import { darkTheme, lightTheme, type ColorScheme, type Theme } from "./theme";

type ThemeContextValue = {
  theme: Theme;
  scheme: ColorScheme;
  /** True when the OS asks for reduced motion; signature animations honor it. */
  reduceMotion: boolean;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

type Props = {
  children: ReactNode;
  /** Force a scheme (tests, previews). Otherwise follow the OS, defaulting dark. */
  forceScheme?: ColorScheme;
};

export function ThemeProvider({ children, forceScheme }: Props) {
  const osScheme = useColorScheme();
  // Holofy is dark-first: only an explicit OS "light" flips us; null defaults dark.
  const scheme: ColorScheme = forceScheme ?? (osScheme === "light" ? "light" : "dark");

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
    () => ({ theme: scheme === "light" ? lightTheme : darkTheme, scheme, reduceMotion }),
    [scheme, reduceMotion]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  return useThemeContext().theme;
}

export function useReduceMotion(): boolean {
  return useThemeContext().reduceMotion;
}

function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>.");
  return ctx;
}
