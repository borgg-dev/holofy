import type { ReactNode } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets, type Edge } from "react-native-safe-area-context";

import { useTheme } from "@/theme";

type Props = {
  children: ReactNode;
  /** "vault" paints the radial Vault-depth ground; "flat" is the plain bg. */
  ground?: "vault" | "flat";
  /**
   * Safe-area edges to gutter. Each listed edge gets `inset + a design gutter` so content
   * never hugs an edge — on web (inset 0) the design gutter alone keeps it clear; on a
   * notched device the inset stacks on top. Camera screens opt out with `edges={[]}` to go
   * full-bleed and clear the safe area on their own controls.
   */
  edges?: readonly Edge[];
  /** Apply the standard horizontal page gutter. On by default; full-bleed screens pass false. */
  padded?: boolean;
  style?: ViewStyle;
};

const DEFAULT_EDGES = ["top", "bottom"] as const;

// Every content screen mounts inside this. It owns the Vault background and — crucially — the
// spacing contract: a comfortable gutter on each safe-area edge (the device inset plus a design
// token), and one standard horizontal page gutter. Spacing lives here so screens don't re-derive
// it and nothing ends up flush to an edge. The "vault" ground is the token's radial depth — a
// violet-tinted near-black, never a flat black.
export function Screen({
  children,
  ground = "vault",
  edges = DEFAULT_EDGES,
  padded = true,
  style,
}: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  // The design gutter sits on top of the raw safe-area inset so the first/last element always
  // breathes, even where the inset is 0 (web, non-notched devices). Horizontal edges use the
  // page gutter; vertical edges use a slightly larger one so headers and action rows clear the
  // status bar / home indicator comfortably.
  const has = (edge: Edge) => edges.includes(edge);
  const sidePad = padded ? theme.space["5"] : 0;
  const layout: ViewStyle = {
    paddingTop: has("top") ? insets.top + theme.space["6"] : 0,
    paddingBottom: has("bottom") ? insets.bottom + theme.space["5"] : 0,
    paddingLeft: (has("left") ? insets.left : 0) + sidePad,
    paddingRight: (has("right") ? insets.right : 0) + sidePad,
  };

  return (
    <View style={[styles.root, { backgroundColor: theme.color.bg }]}>
      {ground === "vault" ? <VaultGround /> : null}
      <View style={[styles.safe, layout, style]}>{children}</View>
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
