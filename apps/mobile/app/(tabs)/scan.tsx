import { useRouter } from "expo-router";

import { useApi, type CaptureImage } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { ScanScreen } from "@/screens/scan/ScanScreen";

// The Scan tab — the live capture frame. A locked shutter captures a still, uploads it for a
// reference, runs recognition on that reference, and routes by outcome: a confident match →
// the foil reveal, an ambiguous one → the confirm chooser. One path on device (real camera +
// server) and in the demo build (the fixture client mints the reference and alternates the
// outcome). Stack mode hands off to the rapid scanner.
export default function ScanTab() {
  const router = useRouter();
  const api = useApi();
  const { runScan } = useScanFlow();

  return (
    <ScanScreen
      onStackMode={() => router.push("/rapid")}
      onCaptured={async (image: CaptureImage) => {
        const { ref } = await api.uploadCapture([image]);
        const result = await runScan(ref);
        if (!result) return; // error state is held in the flow; stay on scan to retry.
        router.push(result.outcome === "resolved" ? "/reveal" : "/confirm");
      }}
    />
  );
}
