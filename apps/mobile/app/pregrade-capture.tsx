import { useState } from "react";
import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { GuidedCaptureScreen } from "@/screens/pregrade/GuidedCaptureScreen";

// Guided multi-angle capture, the entry to the pre-grade sub-flow. Reached from the reveal
// screen's "Pre-grade this card" action; needs a card in hand, so a cold land bounces to
// the scanner. Once every angle is captured it runs the pre-grade on the bundle and routes
// to the gauge, which renders the estimate or the retake outcome.
//
// The mock alternates a clean bundle with a sub-threshold one so both the estimated and the
// retake paths are reachable in the demo build; on device the ref comes from the real
// capture pipeline and the outcome is the model's, not a scripted alternation.
const CAPTURE_REFS = ["mock-capture-clean", "mock-capture-retake"] as const;

export default function PregradeCapture() {
  const router = useRouter();
  const { revealChoice, runPregrade } = useScanFlow();
  const [attempts, setAttempts] = useState(0);

  if (!revealChoice) return <Redirect href="/" />;

  return (
    <GuidedCaptureScreen
      onBack={() => router.back()}
      onComplete={async () => {
        const captureRef = CAPTURE_REFS[attempts % CAPTURE_REFS.length]!;
        setAttempts((n) => n + 1);
        await runPregrade(captureRef);
        router.replace("/pregrade");
      }}
    />
  );
}
