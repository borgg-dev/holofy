import { useCallback, useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useApi, type CollectionItem } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { CardDetailScreen } from "@/screens/detail/CardDetailScreen";

// A Vault holding's detail route. The list passes the holding id; there's no single-item
// endpoint yet, so the screen resolves it from the collection (the fixture and the future
// API both return the full list cheaply). Opening a card seeds the flow's reveal slot with
// its identity + price, so the pre-grade / authenticity actions re-enter the guided capture
// against *this* card exactly as they do from a fresh scan.
type DetailState = "loading" | "missing" | { item: CollectionItem };

export default function CardDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const api = useApi();
  const { confirmChoice } = useScanFlow();
  const [state, setState] = useState<DetailState>("loading");

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const items = await api.listCollection();
        const item = items.find((it) => it.id === id) ?? null;
        if (!active) return;
        setState(item ? { item } : "missing");
        // Seed the flow so a grade/authenticity launched from here knows which card it's of.
        if (item) {
          confirmChoice({
            identity: item.identity,
            confidence: 1,
            price: item.price,
          });
        }
      } catch {
        if (active) setState("missing");
      }
    })();
    return () => {
      active = false;
    };
  }, [api, id, confirmChoice]);

  const back = useCallback(
    () => (router.canGoBack() ? router.back() : router.replace("/")),
    [router]
  );

  return (
    <CardDetailScreen
      state={state}
      onBack={back}
      onGrade={() => router.push("/pregrade-capture")}
      onAuthenticity={() => router.push("/authenticity-capture")}
    />
  );
}
