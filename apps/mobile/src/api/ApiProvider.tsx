import { createContext, useContext, useMemo, type ReactNode } from "react";

import { createFixtureClient, createHttpClient, type HolofyClient } from "./client";
import type { TokenProvider } from "./auth";

// Hands the chosen HolofyClient to the tree. With no live backend configured this is the
// fixture client so every screen and the full flow run offline (the demo); in `http` mode it
// talks to the real API, reading the live session bearer through `getToken` (supplied by the
// AuthProvider), so a login changes the bearer without rebuilding the client. Screens call
// `useApi()`, never construct a client.

type ApiContextValue = { client: HolofyClient };

const ApiContext = createContext<ApiContextValue | null>(null);

type Props =
  | { children: ReactNode; mode?: "fixture"; latencyMs?: number }
  | { children: ReactNode; mode: "http"; baseUrl: string; getToken: TokenProvider };

export function ApiProvider(props: Props) {
  const client = useMemo<HolofyClient>(() => {
    if (props.mode === "http") {
      return createHttpClient({ baseUrl: props.baseUrl, getToken: props.getToken });
    }
    return createFixtureClient({ latencyMs: props.mode === undefined ? undefined : props.latencyMs });
  }, [props]);

  const value = useMemo(() => ({ client }), [client]);
  return <ApiContext.Provider value={value}>{props.children}</ApiContext.Provider>;
}

export function useApi(): HolofyClient {
  const ctx = useContext(ApiContext);
  if (!ctx) throw new Error("useApi must be used within <ApiProvider>.");
  return ctx.client;
}
