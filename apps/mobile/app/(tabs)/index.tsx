import { useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { VaultScreen } from "@/screens/vault/VaultScreen";

// The home tab — the Vault. Lands here on open. Refetches whenever the flow's vaultRevision
// bumps (i.e. after an Add), so a card added on the reveal screen is reflected here at once.
// A holding tapped opens its detail; the stack scanner and the start-here actions route over
// the tabs. The Scan tab carries the camera, so the Vault keeps its buttons to the stack
// shortcut and the empty-state starter — no redundant "Scan" cluttering the value surface.
export default function VaultTab() {
  const router = useRouter();
  const { vaultRevision } = useScanFlow();

  return (
    <VaultScreen
      revision={vaultRevision}
      onScan={() => router.navigate("/scan")}
      onRapidScan={() => router.push("/rapid")}
      onOpenCard={(id) => router.push(`/card/${id}`)}
    />
  );
}
