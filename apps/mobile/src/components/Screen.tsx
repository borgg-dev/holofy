import type { ReactNode } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import { SafeAreaView, type Edge } from "react-native-safe-area-context";

import { useTheme } from "@/theme";

type Props = {
  children: ReactNode;
  /** "vault" paints the radial Vault-depth ground; "flat" is the plain bg. */
  ground?: "vault" | "flat";
  /** Safe-area edges to inset. Camera screens opt out (edges={[]}) to go full-bleed. */
  edges?: readonly Edge[];
  padded?: boolean;
  style?: ViewStyle;
};

// Every screen mounts inside this. It owns the Vault background and safe-area
// insets so individual screens don't re-derive the ground. The "vault" ground is
// the token's radial depth — a violet-tinted near-black, never a flat black.
export function Screen({
  children,
  ground = "vault",
  edges = ["top", "bottom"],
  padded = false,
  style,
}: Props) {
  const theme = useTheme();
  return (
    <View style={[styles.root, { backgroundColor: theme.color.bg }]}>
      {ground === "vault" ? <VaultGround /> : null}
      <SafeAreaView
        edges={edges}
        style={[styles.safe, padded ? { paddingHorizontal: theme.space["5"] } : null, style]}
      >
        {children}
      </SafeAreaView>
    </View>
  );
}

// Approximates --gradient-vault-depth (radial, violet-tinted top) with stacked
// translucent fills — no gradient dependency needed for a static ground. The
// signature conic foil sweep is a separate, deliberately scarce component.
function VaultGround() {
  const theme = useTheme();
  if (theme.scheme === "light") return null;
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.vaultGlow, { backgroundColor: theme.color.vaultGlow }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  safe: { flex: 1 },
  vaultGlow: {
    position: "absolute",
    top: -160,
    left: -40,
    right: -40,
    height: 360,
    borderRadius: 360,
    opacity: 0.5,
  },
});
