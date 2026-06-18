// The auth seam. The backend authenticates a bearer token (apps/api dev-token backend,
// ADR 0003) and will move to federated identity behind the same header later. The app
// only needs "give me the current bearer", so that's the whole interface — a function,
// swappable for one that reads a Keychain/SecureStore session once real sign-in lands.

export type TokenProvider = () => string | null;

/**
 * Dev token provider. The seeded dev user's bearer is injected at app config time
 * (never hardcoded into a screen); until sign-in exists this is how requests are scoped
 * to a user. Returns null when unset so the client sends no Authorization header rather
 * than an empty one.
 */
export function devTokenProvider(token: string | null): TokenProvider {
  return () => token;
}

export function authHeader(provider: TokenProvider): Record<string, string> {
  const token = provider();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
