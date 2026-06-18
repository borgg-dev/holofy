import { useState } from "react";
import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { RevealScreen } from "@/screens/reveal/RevealScreen";

// The foil reveal route. Reads the resolved/confirmed card from the flow and renders the
// payoff. "Add to Vault" commits it and routes to the Vault, where the new value lands.
export default function Reveal() {
  const router = useRouter();
  const { revealChoice, addToVault } = useScanFlow();
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);

  // Land directly without a scan (deep link / refresh) → send back to the scanner.
  if (!revealChoice) return <Redirect href="/" />;

  return (
    <RevealScreen
      identity={revealChoice.identity}
      price={revealChoice.price}
      added={added}
      busy={busy}
      onAdd={async () => {
        setBusy(true);
        const ok = await addToVault(revealChoice.identity);
        setBusy(false);
        if (ok) {
          setAdded(true);
          router.replace("/vault");
        }
      }}
      onGrade={() => router.push("/pregrade-capture")}
      onBack={() => router.replace("/")}
    />
  );
}
