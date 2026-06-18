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
// first paint, and wrap the app in the theme + safe-area providers. Routes are
// declared headerless — screens own their own chrome (the Foil Vault has no
// default nav bar).
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
              />
            </ScanFlowProvider>
          </ApiProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
