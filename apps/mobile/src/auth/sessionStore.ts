// Persisted session bearer. The signed-in token survives an app restart so a client doesn't
// re-login every launch; it's namespaced so it never collides with other prefs. Reads/writes
// fail soft — a storage error degrades to "signed out", never crashes the app.
//
// AsyncStorage is not a secure enclave; a longer-term hardening is expo-secure-store (Keychain
// / Keystore). The store is isolated behind this tiny module so that swap is a one-file change.

import AsyncStorage from "@react-native-async-storage/async-storage";

export const SESSION_TOKEN_KEY = "holofy.session.token";

export async function loadToken(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(SESSION_TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function saveToken(token: string): Promise<void> {
  try {
    await AsyncStorage.setItem(SESSION_TOKEN_KEY, token);
  } catch {
    // A failed persist isn't fatal — the in-memory session still works for this run.
  }
}

export async function clearToken(): Promise<void> {
  try {
    await AsyncStorage.removeItem(SESSION_TOKEN_KEY);
  } catch {
    // Nothing to do — a failed clear is surfaced only as a stale token on next launch, which
    // the /auth/me validation on boot catches anyway.
  }
}
