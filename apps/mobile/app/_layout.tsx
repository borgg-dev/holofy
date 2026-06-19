import { useEffect } from "react";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ApiProvider } from "@/api";
import { ScanFlowProvider } from "@/flow/ScanFlowProvider";
import { ThemeProvider, fontAssets, useTheme } from "@/theme";

// Root layout: load the brand fonts, paint the Vault under the navigator before
// first paint, and wrap the app in the theme + safe-area providers. The root stack
// holds the (tabs) home shell plus the flow screens, which present over the tabs as
// full-screen routes. Everything is headerless — screens own their own chrome (the
// Foil Vault has no default nav bar).
export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(fontAssets);

  // Hold first paint until fonts resolve so headlines don't reflow from a fallback.
  if (!fontsLoaded && !fontError) return null;

  // Fixture-backed by default so the whole scan→reveal→Vault flow runs with no server
  // (make mobile-watch). Set EXPO_PUBLIC_API_URL to point the same screens at a live backend
  // (the in-house recognizer + grader); EXPO_PUBLIC_DEV_TOKEN carries the dev bearer for it.
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  const devToken = process.env.EXPO_PUBLIC_DEV_TOKEN ?? null;
  const tree = (
    <ScanFlowProvider>
      <AppShell />
    </ScanFlowProvider>
  );

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          {apiUrl ? (
            <ApiProvider mode="http" baseUrl={apiUrl} devToken={devToken}>
              {tree}
            </ApiProvider>
          ) : (
            <ApiProvider>{tree}</ApiProvider>
          )}
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

// The themed navigator shell. Lives under ThemeProvider so the status-bar contrast and the
// navigator's container fill track the active scheme — light text on the Vault in dark, dark
// text on the pale ground in light — and re-paint the moment the appearance mode changes.
function AppShell() {
  const theme = useTheme();

  useEffect(() => {
    // Paint the navigator container in the active bg so route transitions never flash.
    void SystemUI.setBackgroundColorAsync(theme.color.bg);
  }, [theme.color.bg]);

  return (
    <>
      <StatusBar style={theme.scheme === "dark" ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: theme.color.bg },
          animation: "fade",
        }}
      >
        <Stack.Screen name="(tabs)" />
        {/* Capture + payoff routes ride over the tabs. The card flows fade in like
            the tabs; the camera screens slide so the hand-off to capture reads as a
            deliberate move into a tool, not a tab switch. */}
        <Stack.Screen name="reveal" />
        <Stack.Screen name="confirm" />
        <Stack.Screen name="card/[id]" />
        <Stack.Screen name="pregrade" />
        <Stack.Screen name="pregrade-capture" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="authenticity" />
        <Stack.Screen name="authenticity-capture" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="rapid" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="rapid-review" />
        <Stack.Screen name="privacy" options={{ animation: "slide_from_right" }} />
      </Stack>
    </>
  );
}
