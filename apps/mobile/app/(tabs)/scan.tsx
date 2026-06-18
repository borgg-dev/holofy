import { useState } from "react";
import { useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { ScanScreen } from "@/screens/scan/ScanScreen";

// The Scan tab — the live capture frame. A locked capture runs recognition and routes by
// outcome over the tabs: a confident match → the foil reveal, an ambiguous one → the confirm
// chooser. The mock alternates bundles so both paths are reachable in the demo build; on device
// the bundle id comes from the real capture pipeline. Stack mode hands off to the rapid scanner.
const BUNDLES = ["mock-high-confidence", "mock-needs-confirmation"] as const;

export default function ScanTab() {
  const router = useRouter();
  const { runScan } = useScanFlow();
  const [captures, setCaptures] = useState(0);

  return (
    <ScanScreen
      onStackMode={() => router.push("/rapid")}
      onCaptured={async () => {
        const bundleId = BUNDLES[captures % BUNDLES.length]!;
        setCaptures((n) => n + 1);
        const result = await runScan(bundleId);
        if (!result) return; // error state is held in the flow; stay on scan to retry.
        router.push(result.outcome === "resolved" ? "/reveal" : "/confirm");
      }}
    />
  );
}
