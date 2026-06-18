import * as Haptics from "expo-haptics";
import { Platform } from "react-native";

// expo-haptics throws on web ("Haptic.impactAsync is not available on web"). These wrappers
// no-op there so the same call sites work on native and web. Callers keep their own
// reduced-motion / context guards; this only guards the platform.
const supported = Platform.OS !== "web";

export function impactLight(): void {
  if (supported) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
}

export function impactMedium(): void {
  if (supported) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
}

export function notifyWarning(): void {
  if (supported) void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
}
