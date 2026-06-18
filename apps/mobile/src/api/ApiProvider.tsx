import { createContext, useContext, useMemo, type ReactNode } from "react";

import { createFixtureClient, createHttpClient, type HolofyClient } from "./client";
import { devTokenProvider } from "./auth";

// Hands the chosen HolofyClient to the tree. Until a live backend is reachable from the
// app, this defaults to the fixture client so every screen and the full flow run offline;
// pointing at staging/prod is a `mode="http"` + baseUrl change here, with the auth seam
// already in place. Screens call `useApi()`, never construct a client.

type ApiContextValue = { client: HolofyClient };

const ApiContext = createContext<ApiContextValue | null>(null);

type Props =
  | { children: ReactNode; mode?: "fixture"; latencyMs?: number }
  | { children: ReactNode; mode: "http"; baseUrl: string; devToken?: string | null };

export function ApiProvider(props: Props) {
  const client = useMemo<HolofyClient>(() => {
    if (props.mode === "http") {
      return createHttpClient({
        baseUrl: props.baseUrl,
        getToken: devTokenProvider(props.devToken ?? null),
      });
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
