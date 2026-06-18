import { useEffect } from "react";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ApiProvider } from "@/api";
import { ScanFlowProvider } from "@/flow/ScanFlowProvider";
import { ThemeProvider, darkTheme, fontAssets } from "@/theme";

// Root layout: load the brand fonts, paint the Vault under the navigator before
// first paint, and wrap the app in the theme + safe-area providers. The root stack
// holds the (tabs) home shell plus the flow screens, which present over the tabs as
// full-screen routes. Everything is headerless — screens own their own chrome (the
// Foil Vault has no default nav bar).
export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(fontAssets);

  useEffect(() => {
    // Paint the navigator container in the Vault so route transitions never flash.
    void SystemUI.setBackgroundColorAsync(darkTheme.color.bg);
  }, []);

  // Hold first paint until fonts resolve so headlines don't reflow from a fallback.
  if (!fontsLoaded && !fontError) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          {/* Fixture-backed by default so the whole scan→reveal→Vault flow runs with no
              server; pointing at staging is a `mode="http"` + baseUrl change here. */}
          <ApiProvider>
            <ScanFlowProvider>
              <StatusBar style="light" />
              <Stack
                screenOptions={{
                  headerShown: false,
                  contentStyle: { backgroundColor: darkTheme.color.bg },
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
            </ScanFlowProvider>
          </ApiProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
