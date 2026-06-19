import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { createHttpClient, type HolofyClient } from "@/api/client";
import { ApiError } from "@/api/errors";
import type { AuthAccount, Credentials } from "@/api/models";

import { clearToken, loadToken, saveToken } from "./sessionStore";

// The session owner. Holds the bearer (in a ref so the API client always reads the *live*
// token without rebuilding), validates a persisted token on launch, and exposes sign-in /
// register / sign-out. The rest of the app reads the token through `getToken`, so the one
// HolofyClient stays authed as the session changes — no client churn on login.

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthValue = {
  status: AuthStatus;
  user: AuthAccount | null;
  /** Live bearer accessor for the app's API client. Null when signed out. */
  getToken: () => string | null;
  signIn: (credentials: Credentials) => Promise<void>;
  register: (credentials: Credentials) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ baseUrl, children }: { baseUrl: string; children: ReactNode }) {
  const tokenRef = useRef<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthAccount | null>(null);

  // One client, reading the live token from the ref — so a login updates auth without
  // reconstructing the client the whole app shares.
  const client = useMemo<HolofyClient>(
    () => createHttpClient({ baseUrl, getToken: () => tokenRef.current }),
    [baseUrl]
  );

  const setSession = useCallback((token: string, account: AuthAccount) => {
    tokenRef.current = token;
    setUser(account);
    setStatus("authenticated");
  }, []);

  // On launch: restore a persisted token and confirm it still resolves to an account. A
  // missing or rejected token lands on the sign-in screen; a transient network failure does
  // *not* sign the user out (we keep the token and let the app retry).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const stored = await loadToken();
      if (cancelled) return;
      if (!stored) {
        setStatus("unauthenticated");
        return;
      }
      tokenRef.current = stored;
      try {
        const account = await client.currentUser();
        if (!cancelled) setSession(stored, account);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === "unauthorized") {
          tokenRef.current = null;
          await clearToken();
          setStatus("unauthenticated");
        } else {
          // Offline / server hiccup: trust the stored token rather than forcing a re-login.
          setStatus("authenticated");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, setSession]);

  const enter = useCallback(
    async (credentials: Credentials, kind: "signIn" | "register") => {
      const session =
        kind === "register"
          ? await client.register(credentials)
          : await client.login(credentials);
      await saveToken(session.token);
      setSession(session.token, session.user);
    },
    [client, setSession]
  );

  const signIn = useCallback((c: Credentials) => enter(c, "signIn"), [enter]);
  const register = useCallback((c: Credentials) => enter(c, "register"), [enter]);

  const signOut = useCallback(async () => {
    tokenRef.current = null;
    setUser(null);
    await clearToken();
    setStatus("unauthenticated");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, user, getToken: () => tokenRef.current, signIn, register, signOut }),
    [status, user, signIn, register, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>.");
  return ctx;
}

/**
 * Like {@link useAuth} but returns null instead of throwing when there's no provider — for UI
 * that's shared between live mode (gated by AuthProvider) and the demo (no auth), e.g. the
 * Settings sign-out, which simply doesn't render when there's no session to end.
 */
export function useOptionalAuth(): AuthValue | null {
  return useContext(AuthContext);
}
