import { Redirect, useLocalSearchParams, useRouter } from "expo-router";

import { useApi } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { GuidedCaptureScreen } from "@/screens/pregrade/GuidedCaptureScreen";

// Guided multi-angle capture, the entry to the pre-grade sub-flow. Reached from the reveal
// screen's "Pre-grade this card" action; needs a card in hand, so a cold land bounces to
// the scanner. Once every angle is captured it uploads the real stills, runs the pre-grade on
// the returned reference, and routes to the gauge (the model's estimate or a retake) — exactly
// like the scan tab. On web/demo the fixture upload mints a reference and the fixture pre-grade
// answers, so the same path runs offline.
export default function PregradeCapture() {
  const router = useRouter();
  const api = useApi();
  const { revealChoice, runPregrade } = useScanFlow();
  // When launched from a Vault card, the holding id rides along so the detected condition is
  // written back onto that card (the Vault then reflects what the app assessed).
  const { holdingId } = useLocalSearchParams<{ holdingId?: string }>();

  if (!revealChoice) return <Redirect href="/scan" />;

  return (
    <GuidedCaptureScreen
      onBack={() => router.back()}
      onComplete={async (stills) => {
        const { ref } = await api.uploadCapture(stills);
        await runPregrade(ref, holdingId ?? null);
        router.replace("/pregrade");
      }}
    />
  );
}
