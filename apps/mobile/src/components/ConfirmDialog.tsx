import { Modal, Pressable, StyleSheet, View } from "react-native";

import { useTheme } from "@/theme";
import { Button } from "./Button";
import { FoilSurface } from "./FoilSurface";
import { Text } from "./Text";

// A fixed dark wash behind the dialog — a scrim must darken under the card in either scheme,
// so it isn't drawn from the (scheme-flipping) background token.
const SCRIM = "rgba(0, 0, 0, 0.66)";

type Props = {
  visible: boolean;
  title: string;
  /** The supporting line under the title — the consequence, stated plainly. */
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Paints the confirm action in the error red — for deletes and other irreversibles. */
  destructive?: boolean;
  /** Disables the actions and shows the confirm's spinner while the action is in flight. */
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

// The house confirmation dialog — the in-app replacement for the OS Alert, so a destructive
// choice is asked in the Vault's own near-black surface and type rather than a generic system
// pop-up. A tapped scrim or the hardware back cancels (the safe default); the confirm carries
// the error-red and the busy state for the round-trip.
export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  const theme = useTheme();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={busy ? undefined : onCancel}
    >
      <View style={styles.fill}>
        {/* The scrim — tapping outside the card cancels, the way a sheet dismisses. Always a
            dark wash (even in light mode) so the floating Vault card reads as lifted. */}
        <Pressable
          style={[styles.scrim, { backgroundColor: SCRIM }]}
          onPress={busy ? undefined : onCancel}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
        <View style={styles.center} pointerEvents="box-none">
          <View
            style={[styles.card, { maxWidth: 360 }]}
            accessibilityViewIsModal
            accessibilityRole="alert"
          >
            <FoilSurface level="elevated" padded>
              <View style={{ gap: theme.space["3"] }}>
                <Text variant="titleMd" tone="primary">
                  {title}
                </Text>
                {message ? (
                  <Text variant="bodySm" tone="secondary">
                    {message}
                  </Text>
                ) : null}
                <View style={{ gap: theme.space["3"], marginTop: theme.space["3"] }}>
                  <Button
                    label={confirmLabel}
                    tier="primary"
                    destructive={destructive}
                    busy={busy}
                    onPress={onConfirm}
                  />
                  <Button label={cancelLabel} tier="tertiary" disabled={busy} onPress={onCancel} />
                </View>
              </View>
            </FoilSurface>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  scrim: { ...StyleSheet.absoluteFillObject },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  card: { width: "100%" },
});
