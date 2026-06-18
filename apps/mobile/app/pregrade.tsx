import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import {
  PregradeComputing,
  PregradeError,
  PregradeGaugeScreen,
} from "@/screens/pregrade/PregradeGaugeScreen";
import { RetakeScreen } from "@/screens/pregrade/RetakeScreen";

// The pre-grade result route. Renders by the flow's pregrade state: assessing → the staged
// computing skeleton, error → a retry, ready → the gauge (estimated) or the coaching screen
// (retake). Both retake's re-scan and the gauge's back route into a fresh guided capture, so
// the honest "let's get a cleaner shot" loop has somewhere to go.
export default function Pregrade() {
  const router = useRouter();
  const { pregrade, resetPregrade } = useScanFlow();

  const reScan = () => {
    resetPregrade();
    router.replace("/pregrade-capture");
  };

  // Return to whichever card surface launched this — the reveal or the Vault card detail —
  // since pre-grade is reachable from both. The capture screen replaced itself with this
  // result, so the card screen is still directly beneath in the stack.
  const toCard = () => (router.canGoBack() ? router.back() : router.replace("/reveal"));

  switch (pregrade.status) {
    case "assessing":
      return <PregradeComputing />;
    case "error":
      // Re-running needs a fresh capture ref; sending back to capture re-arms the flow.
      return <PregradeError onRetry={reScan} onBack={toCard} />;
    case "ready":
      return pregrade.result.status === "estimated" ? (
        <PregradeGaugeScreen
          estimate={pregrade.result}
          onLogGrade={() => {
            // P2.3 — consent-gated real-grade logging feeds the data moat.
          }}
          onWhatAffects={() => {
            // P2.3 — the per-axis explainer sheet.
          }}
          onBack={toCard}
        />
      ) : (
        <RetakeScreen retake={pregrade.result} onRescan={reScan} onBack={toCard} />
      );
    default:
      // Idle / cold land — no assessment in flight, send back to the card.
      return <Redirect href="/reveal" />;
  }
}
