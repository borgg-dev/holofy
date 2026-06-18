import { useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { RapidScanScreen } from "@/screens/rapid/RapidScanScreen";

// The rapid/stack capture route. The collector flips a pile, each capture landing on the live
// filmstrip; "Review stack" runs POST /scan/batch on the flipped refs and continues to the
// confirm-at-end review. Reached from the scan screen's Stack mode (or a Vault action).
export default function Rapid() {
  const router = useRouter();
  const { runBatchScan } = useScanFlow();

  return (
    <RapidScanScreen
      onBack={() => (router.canGoBack() ? router.back() : router.replace("/scan"))}
      onReview={async (captureRefs) => {
        // Kick the batch off and move on — the review renders the loading state while it lands,
        // and the flow holds the result so a back-nav never re-runs recognition.
        void runBatchScan(captureRefs);
        router.push("/rapid-review");
      }}
    />
  );
}
