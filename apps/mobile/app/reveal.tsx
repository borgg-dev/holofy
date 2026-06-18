import { useState } from "react";
import { View } from "react-native";
import { Redirect, useRouter } from "expo-router";

import { useApi } from "@/api";
import { useScanFlow } from "@/flow/ScanFlowProvider";
import { RevealScreen } from "@/screens/reveal/RevealScreen";
import { FirstCapturePrompt } from "@/screens/privacy/FirstCapturePrompt";
import { CONSENT_COPY_VERSION } from "@/screens/privacy/copy";

// The foil reveal route. Reads the resolved/confirmed card from the flow and renders the
// payoff. "Add to Vault" commits it and routes to the Vault, where the new value lands.
//
// After the *first* scan settles into a reveal, the one-time training-consent prompt is shown
// over the payoff — in context, once, default-decline. Choosing yes sets the session consent
// (so later captures opt in) and records the account-level grant; either choice dismisses it.
export default function Reveal() {
  const router = useRouter();
  const api = useApi();
  const { revealChoice, addToVault, trainingConsent, setTrainingConsent, consentPromptSeen, markConsentPromptSeen } =
    useScanFlow();
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);

  // Land directly without a scan (deep link / refresh) → send to the scanner tab.
  if (!revealChoice) return <Redirect href="/scan" />;

  const showPrompt = !consentPromptSeen && !trainingConsent;

  return (
    <View style={{ flex: 1 }}>
      <RevealScreen
        identity={revealChoice.identity}
        price={revealChoice.price}
        added={added}
        busy={busy}
        onAdd={async () => {
          setBusy(true);
          const ok = await addToVault(revealChoice.identity);
          setBusy(false);
          if (ok) {
            setAdded(true);
            router.replace("/");
          }
        }}
        onGrade={() => router.push("/pregrade-capture")}
        onAuthenticity={() => router.push("/authenticity-capture")}
        onBack={() => router.replace("/scan")}
      />
      {showPrompt ? (
        <FirstCapturePrompt
          onAccept={() => {
            setTrainingConsent(true);
            markConsentPromptSeen();
            // Persist the account-level grant; the UI choice is the source of truth, so a
            // failed write is swallowed — the user can confirm it in the privacy screen.
            void api.setTrainingConsent({ granted: true, note: CONSENT_COPY_VERSION }).catch(() => {});
          }}
          onDecline={markConsentPromptSeen}
        />
      ) : null}
    </View>
  );
}
