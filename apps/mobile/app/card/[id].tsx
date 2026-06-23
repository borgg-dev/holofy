import { useCallback, useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useApi, type CollectionItem } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { ConfirmDialog } from "@/components";
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
  const { confirmChoice, notifyVaultChanged } = useScanFlow();
  const [state, setState] = useState<DetailState>("loading");
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const [removing, setRemoving] = useState(false);

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

  // Removing a holding is destructive, so it goes behind the themed confirm dialog rather than
  // a one-tap action. On confirm we delete, signal the Vault to refetch (it stays mounted behind
  // this route, so it wouldn't otherwise notice), then return to it — which now reflects the change.
  const confirmRemove = useCallback(() => {
    if (!id) return;
    setRemoving(true);
    void (async () => {
      try {
        await api.removeFromCollection(id);
        notifyVaultChanged();
      } catch {
        // Surface nothing noisy here; returning to the Vault re-fetches the true state.
      } finally {
        setRemoving(false);
        setConfirmingRemove(false);
        back();
      }
    })();
  }, [api, id, notifyVaultChanged, back]);

  return (
    <>
      <CardDetailScreen
        state={state}
        onBack={back}
        onGrade={() => router.push({ pathname: "/pregrade-capture", params: { holdingId: id } })}
        onAuthenticity={() => router.push("/authenticity-capture")}
        onRemove={() => setConfirmingRemove(true)}
      />
      <ConfirmDialog
        visible={confirmingRemove}
        title="Remove from Vault?"
        message="This card will be removed from your collection. You can always scan it back in."
        confirmLabel="Remove"
        cancelLabel="Cancel"
        destructive
        busy={removing}
        onConfirm={confirmRemove}
        onCancel={() => setConfirmingRemove(false)}
      />
    </>
  );
}
