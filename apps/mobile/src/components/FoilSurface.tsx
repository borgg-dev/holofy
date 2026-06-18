import type { ReactNode } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";

import { useTheme } from "@/theme";

type Props = {
  children: ReactNode;
  /** "elevated" = card/sheet; "raised" = a card-on-card; "inset" = a well/input. */
  level?: "elevated" | "raised" | "inset";
  /** A hairline foil-edge — reserved for surfaces holding a reward/value. */
  foilEdge?: boolean;
  padded?: boolean;
  style?: ViewStyle;
};

// The house surface. A Vault card: elevated near-black with a token border and
// shadow. `foilEdge` adds the one restrained brand cue — a violet top hairline —
// for surfaces that carry a value or reward, keeping foil scarce per the system.
export function FoilSurface({ children, level = "elevated", foilEdge, padded = true, style }: Props) {
  const theme = useTheme();
  const bg =
    level === "raised"
      ? theme.color.bgRaised
      : level === "inset"
        ? theme.color.bgInset
        : theme.color.bgElevated;

  return (
    <View
      style={[
        styles.surface,
        {
          backgroundColor: bg,
          borderColor: theme.color.border,
          borderRadius: theme.radius.lg,
          padding: padded ? theme.space["6"] : 0,
          ...(theme.scheme === "dark" ? shadow : null),
        },
        style,
      ]}
    >
      {foilEdge ? (
        <View
          pointerEvents="none"
          style={[
            styles.foilEdge,
            { backgroundColor: theme.color.holoViolet, borderTopLeftRadius: theme.radius.lg, borderTopRightRadius: theme.radius.lg },
          ]}
        />
      ) : null}
      {children}
    </View>
  );
}

const shadow: ViewStyle = {
  shadowColor: "#000",
  shadowOpacity: 0.45,
  shadowRadius: 16,
  shadowOffset: { width: 0, height: 4 },
  elevation: 6,
};

const styles = StyleSheet.create({
  surface: {
    borderWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
  },
  foilEdge: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 2,
    opacity: 0.9,
  },
});
