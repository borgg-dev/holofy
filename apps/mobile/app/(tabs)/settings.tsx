import { useRouter } from "expo-router";

import { SettingsScreen } from "@/screens/settings/SettingsScreen";

// The Settings tab. Hosts the account block and routes to the privacy / training-consent
// screen, which stays a stack route so it can carry its own back affordance.
export default function SettingsTab() {
  const router = useRouter();
  return <SettingsScreen onPrivacy={() => router.push("/privacy")} />;
}
