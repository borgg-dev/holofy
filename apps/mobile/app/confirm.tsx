import { Redirect, useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { ConfirmScreen } from "@/screens/confirm/ConfirmScreen";

// The low-confidence confirm route. Only reachable when the last scan came back
// needs_confirmation; it renders the top-2 + € delta. Confirming promotes the chosen
// variant into the reveal slot and continues to the foil reveal.
export default function Confirm() {
  const router = useRouter();
  const { scan, confirmChoice } = useScanFlow();

  // Reachable only with an in-hand needs_confirmation result.
  if (scan.status !== "ready" || scan.result.outcome !== "needs_confirmation") {
    return <Redirect href="/" />;
  }

  return (
    <ConfirmScreen
      choices={scan.result.choices}
      priceDelta={scan.result.priceDelta}
      onConfirm={(choice) => {
        confirmChoice(choice);
        router.replace("/reveal");
      }}
      onBack={() => router.replace("/")}
    />
  );
}
