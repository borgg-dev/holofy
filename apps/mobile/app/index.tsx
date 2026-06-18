import { useRouter } from "expo-router";

import { ScanScreen } from "@/screens/scan/ScanScreen";

// The scanner is the app's front door — a returning collector opens Holofy to
// point it at a card, so the index route is the scan frame itself.
export default function Index() {
  const router = useRouter();
  return (
    <ScanScreen
      onBack={() => (router.canGoBack() ? router.back() : undefined)}
      onCaptured={() => {
        // P1.4 routes a locked capture into the recognize→value flow.
      }}
    />
  );
}
