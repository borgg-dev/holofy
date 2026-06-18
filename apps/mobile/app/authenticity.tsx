import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { VerdictScreen } from "@/screens/authenticity/VerdictScreen";
import {
  ScreeningError,
  ScreeningNotAssessed,
  ScreeningRetake,
  ScreeningState,
} from "@/screens/authenticity/StatusScreens";

// The authenticity result route. Renders by the flow's authenticity state: screening → the
// staged skeleton, error → a retry, ready → the verdict shield (assessed), the coaching
// screen (retake), or the calm below-threshold screen (notAssessed). Re-shoot paths route
// back into a fresh guided capture so the "let's get cleaner shots" loop has somewhere to go.
export default function Authenticity() {
  const router = useRouter();
  const { authenticity, resetAuthenticity } = useScanFlow();

  const reShoot = () => {
    resetAuthenticity();
    router.replace("/authenticity-capture");
  };

  const toCard = () => router.replace("/reveal");

  switch (authenticity.status) {
    case "screening":
      return <ScreeningState />;
    case "error":
      // Re-running needs a fresh capture ref; sending back to capture re-arms the flow.
      return <ScreeningError onRetry={reShoot} onBack={toCard} />;
    case "ready":
      switch (authenticity.result.status) {
        case "assessed":
          return (
            <VerdictScreen
              assessment={authenticity.result}
              onAuthenticate={() => {
                // P3.3 — professional-authentication guidance / out-link.
              }}
              onRescan={reShoot}
              onBack={toCard}
            />
          );
        case "retake":
          return (
            <ScreeningRetake retake={authenticity.result} onRescan={reShoot} onBack={toCard} />
          );
        case "notAssessed":
          return <ScreeningNotAssessed notAssessed={authenticity.result} onBack={toCard} />;
      }
    // eslint-disable-next-line no-fallthrough
    default:
      // Idle / cold land — no screening in flight, send back to the card.
      return <Redirect href="/reveal" />;
  }
}
