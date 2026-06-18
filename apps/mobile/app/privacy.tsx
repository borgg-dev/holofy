import { useRouter } from "expo-router";

import { PrivacyScreen } from "@/screens/privacy/PrivacyScreen";

// The privacy / training-consent route. Reachable from Settings; the setting it manages is
// the user's grip on the data-loop moat, kept off until they explicitly turn it on.
export default function Privacy() {
  const router = useRouter();
  return <PrivacyScreen onBack={() => (router.canGoBack() ? router.back() : router.replace("/settings"))} />;
}
