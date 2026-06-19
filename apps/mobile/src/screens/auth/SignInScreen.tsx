import { useCallback, useMemo, useState } from "react";
import { StyleSheet, TextInput, View } from "react-native";

import { Button, Screen, Text } from "@/components";
import { ApiError } from "@/api/errors";
import { useAuth } from "@/auth/AuthContext";
import { useTheme } from "@/theme";

// The gate the app sits behind in live mode: create an account or sign in. One form, a
// mode toggle, themed inputs, and an honest inline error (the server's message for a wrong
// password / taken email, a friendly fallback for anything else). On success the AuthProvider
// flips to authenticated and the gate reveals the app — no navigation here.

type Mode = "signIn" | "register";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function SignInScreen() {
  const theme = useTheme();
  const { signIn, register } = useAuth();

  const [mode, setMode] = useState<Mode>("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const registering = mode === "register";
  const emailValid = EMAIL_RE.test(email.trim());
  // Mirror the server's 8-char floor so we don't round-trip an obvious reject on register.
  const passwordValid = registering ? password.length >= 8 : password.length >= 1;
  const canSubmit = emailValid && passwordValid && !busy;

  const submit = useCallback(async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const credentials = { email: email.trim(), password };
      await (registering ? register(credentials) : signIn(credentials));
      // No navigation: the gate re-renders to the app once auth status flips.
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Check your connection and try again."
      );
      setBusy(false);
    }
  }, [canSubmit, email, password, registering, register, signIn]);

  const inputStyle = useMemo(
    () => ({
      backgroundColor: theme.color.bgInset,
      borderColor: theme.color.border,
      borderWidth: 1,
      borderRadius: theme.radius.md,
      color: theme.color.textPrimary,
      paddingHorizontal: theme.space["4"],
      minHeight: theme.tapTarget,
    }),
    [theme]
  );

  return (
    <Screen>
      <View style={[styles.root, { gap: theme.space["6"] }]}>
        <View style={{ gap: theme.space["2"] }}>
          <Text variant="displayMd">Holofy</Text>
          <Text variant="body" tone="secondary">
            {registering
              ? "Create an account to start your vault."
              : "Sign in to your vault."}
          </Text>
        </View>

        <View style={{ gap: theme.space["4"] }}>
          <View style={{ gap: theme.space["2"] }}>
            <Text variant="label" tone="secondary">
              Email
            </Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={theme.color.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              inputMode="email"
              accessibilityLabel="Email"
              style={inputStyle}
              editable={!busy}
            />
          </View>

          <View style={{ gap: theme.space["2"] }}>
            <Text variant="label" tone="secondary">
              Password
            </Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder={registering ? "At least 8 characters" : "Your password"}
              placeholderTextColor={theme.color.textTertiary}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              textContentType={registering ? "newPassword" : "password"}
              accessibilityLabel="Password"
              style={inputStyle}
              editable={!busy}
              onSubmitEditing={submit}
              returnKeyType="go"
            />
          </View>

          {error ? (
            <Text variant="bodySm" style={{ color: theme.color.errorRed }} accessibilityRole="alert">
              {error}
            </Text>
          ) : null}
        </View>

        <View style={{ gap: theme.space["3"] }}>
          <Button
            label={registering ? "Create account" : "Sign in"}
            onPress={submit}
            disabled={!canSubmit}
            busy={busy}
          />
          <Button
            label={registering ? "I already have an account" : "Create a new account"}
            tier="tertiary"
            disabled={busy}
            onPress={() => {
              setMode(registering ? "signIn" : "register");
              setError(null);
            }}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    justifyContent: "center",
  },
});
