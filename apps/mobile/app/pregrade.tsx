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

  switch (pregrade.status) {
    case "assessing":
      return <PregradeComputing />;
    case "error":
      // Re-running needs a fresh capture ref; sending back to capture re-arms the flow.
      return <PregradeError onRetry={reScan} onBack={() => router.replace("/reveal")} />;
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
          onBack={() => router.replace("/reveal")}
        />
      ) : (
        <RetakeScreen
          retake={pregrade.result}
          onRescan={reScan}
          onBack={() => router.replace("/reveal")}
        />
      );
    default:
      // Idle / cold land — no assessment in flight, send back to the card.
      return <Redirect href="/reveal" />;
  }
}
