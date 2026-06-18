import { useState } from "react";
import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { GuidedCaptureScreen } from "@/screens/authenticity/GuidedCaptureScreen";

// Guided authenticity capture, the entry to the screening sub-flow. Reached from the reveal
// screen's "Check authenticity" action; needs a resolved card in hand (the catalog
// cross-check + value gate require one), so a cold land bounces to the scanner. Once every
// shot is captured it runs the screening on the bundle and routes to the verdict, which
// renders the band, the retake coaching, or the below-threshold "not needed" state.
//
// The mock cycles the fixture refs so all five outcomes are reachable in the demo build; on
// device the ref comes from the real capture pipeline and the outcome is the service's,
// keyed off the resolved card, never a scripted rotation.
const CAPTURE_REFS = [
  "mock-auth-strong",
  "mock-auth-elevated",
  "mock-auth-inconclusive",
  "mock-auth-retake",
  "mock-auth-not-assessed",
] as const;

export default function AuthenticityCapture() {
  const router = useRouter();
  const { revealChoice, runAuthenticity } = useScanFlow();
  const [attempts, setAttempts] = useState(0);

  if (!revealChoice) return <Redirect href="/scan" />;

  return (
    <GuidedCaptureScreen
      onBack={() => router.back()}
      onComplete={async () => {
        const captureRef = CAPTURE_REFS[attempts % CAPTURE_REFS.length]!;
        setAttempts((n) => n + 1);
        await runAuthenticity(captureRef);
        router.replace("/authenticity");
      }}
    />
  );
}
