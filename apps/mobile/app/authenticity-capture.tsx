import { Redirect, useRouter } from "expo-router";

import { useApi } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { GuidedCaptureScreen } from "@/screens/authenticity/GuidedCaptureScreen";

// Guided authenticity capture, the entry to the screening sub-flow. Reached from the reveal
// screen's "Check authenticity" action; needs a resolved card in hand (the catalog
// cross-check + value gate require one), so a cold land bounces to the scanner. Once every
// shot is captured it uploads the real stills, runs the screening on the returned reference,
// and routes to the verdict (band, retake, or below-threshold). On web/demo the fixture upload
// mints a reference and the fixture screening answers, so the same path runs offline.
export default function AuthenticityCapture() {
  const router = useRouter();
  const api = useApi();
  const { revealChoice, runAuthenticity } = useScanFlow();

  if (!revealChoice) return <Redirect href="/scan" />;

  return (
    <GuidedCaptureScreen
      onBack={() => router.back()}
      onComplete={async (stills) => {
        const { ref } = await api.uploadCapture(stills);
        await runAuthenticity(ref);
        router.replace("/authenticity");
      }}
    />
  );
}
