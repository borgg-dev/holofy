import { useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { VaultScreen } from "@/screens/vault/VaultScreen";

// The Vault route. Refetches whenever the flow's vaultRevision bumps (i.e. after an Add),
// so a card added on the reveal screen is reflected here immediately.
export default function Vault() {
  const router = useRouter();
  const { vaultRevision } = useScanFlow();

  return (
    <VaultScreen
      revision={vaultRevision}
      onScan={() => router.replace("/")}
      onPrivacy={() => router.push("/privacy")}
    />
  );
}
