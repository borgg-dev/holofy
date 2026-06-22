import { useEffect, useState } from "react";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ApiProvider } from "@/api";
import { AuthProvider, useAuth, type AuthStatus } from "@/auth/AuthContext";
import { CurrencyProvider } from "@/currency";
import { ScanFlowProvider } from "@/flow/ScanFlowProvider";
import { ThemeProvider, fontAssets, useTheme } from "@/theme";

// Root layout: load the brand fonts, then mount the app under the theme + safe-area providers.
// Two modes:
//   • Demo (no EXPO_PUBLIC_API_URL): the fixture client, no auth — the whole flow runs offline.
//   • Live (EXPO_PUBLIC_API_URL set): real accounts. AuthProvider owns the session bearer; the
//     navigator redirects an unauthenticated session to /sign-in and back once signed in, and
//     the app's API client reads the live token through `getToken`.
export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(fontAssets);

  // Hold first paint until fonts resolve so headlines don't reflow from a fallback — but never
  // hang on it. If fonts haven't loaded (or errored) within a short window, render anyway with
  // the system font rather than freezing on the splash forever (a font load that stalls must
  // not brick the whole app).
  const [fontTimedOut, setFontTimedOut] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setFontTimedOut(true), 2500);
    return () => clearTimeout(t);
  }, []);
  if (!fontsLoaded && !fontError && !fontTimedOut) return null;

  const apiUrl = process.env.EXPO_PUBLIC_API_URL;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <CurrencyProvider>
            {apiUrl ? (
              <AuthProvider baseUrl={apiUrl}>
                <LiveTree baseUrl={apiUrl} />
              </AuthProvider>
            ) : (
              <ApiProvider>
                <ScanFlowProvider>
                  <AppShell />
                </ScanFlowProvider>
              </ApiProvider>
            )}
          </CurrencyProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

// Live mode: the API client reads the live session token, and the shell gets the auth status
// so it can redirect to/from the sign-in gate.
function LiveTree({ baseUrl }: { baseUrl: string }) {
  const { status, getToken } = useAuth();
  return (
    <ApiProvider mode="http" baseUrl={baseUrl} getToken={getToken}>
      <ScanFlowProvider>
        <AppShell authStatus={status} />
      </ScanFlowProvider>
    </ApiProvider>
  );
}

// The themed navigator shell. Lives under ThemeProvider so the status-bar contrast and the
// navigator's container fill track the active scheme. When `authStatus` is provided (live
// mode) it gates: an unauthenticated session is redirected to /sign-in, and a signed-in one
// off it. In demo mode `authStatus` is undefined and nothing is gated.
function AppShell({ authStatus }: { authStatus?: AuthStatus }) {
  const theme = useTheme();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    // Paint the navigator container in the active bg so route transitions never flash.
    void SystemUI.setBackgroundColorAsync(theme.color.bg);
  }, [theme.color.bg]);

  useEffect(() => {
    if (!authStatus || authStatus === "loading") return;
    const onSignIn = segments[0] === "sign-in";
    if (authStatus === "unauthenticated" && !onSignIn) {
      router.replace("/sign-in");
    } else if (authStatus === "authenticated" && onSignIn) {
      router.replace("/");
    }
  }, [authStatus, segments, router]);

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
        <Stack.Screen name="sign-in" />
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
