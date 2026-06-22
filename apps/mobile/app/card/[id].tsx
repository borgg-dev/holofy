import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";
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

  // Remove this holding, behind a confirm (a Vault deletion is destructive and shouldn't be a
  // one-tap accident). On success — or even if the delete races a refresh — we return to the
  // Vault, which re-fetches and reflects the change.
  const remove = useCallback(() => {
    if (!id) return;
    Alert.alert("Remove from Vault?", "This card will be removed from your collection.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: () => {
          void (async () => {
            try {
              await api.removeFromCollection(id);
            } catch {
              // Surface nothing noisy here; returning to the Vault re-fetches the true state.
            } finally {
              back();
            }
          })();
        },
      },
    ]);
  }, [api, id, back]);

  return (
    <CardDetailScreen
      state={state}
      onBack={back}
      onGrade={() => router.push("/pregrade-capture")}
      onAuthenticity={() => router.push("/authenticity-capture")}
      onRemove={remove}
    />
  );
}
