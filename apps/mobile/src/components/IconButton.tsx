import type { ReactNode } from "react";
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";

import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";

type Props = {
  children: ReactNode;
  onPress?: () => void;
  accessibilityLabel: string;
  style?: StyleProp<ViewStyle>;
};

// A 44pt blurred-disc control for the camera top bar. The translucent inset fill
// lets the preview read behind it; focus/press states come from the token ring.
export function IconButton({ children, onPress, accessibilityLabel, style }: Props) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={6}
      style={({ pressed }) => [
        styles.btn,
        {
          width: theme.tapTarget,
          height: theme.tapTarget,
          borderRadius: theme.radius.pill,
          backgroundColor: withAlpha(theme.color.bgElevated, 0.55),
          opacity: pressed ? 0.7 : 1,
        },
        style,
      ]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { alignItems: "center", justifyContent: "center" },
});
