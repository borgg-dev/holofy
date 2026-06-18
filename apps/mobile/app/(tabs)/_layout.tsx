import { Tabs } from "expo-router";

import { TabBar } from "@/components";

// The persistent home shell: Vault (home), Scan, Settings, behind a bespoke bottom bar.
// The flow screens (reveal, confirm, pre-grade, authenticity, rapid, card detail) are stack
// routes presented over this group, so capture and result payoffs take the full screen while
// the three destinations stay one tap away. Routes are headerless — each screen owns its chrome.
export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{ headerShown: false }}
    >
      <Tabs.Screen name="index" options={{ title: "Vault" }} />
      <Tabs.Screen name="scan" options={{ title: "Scan" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings" }} />
    </Tabs>
  );
}
