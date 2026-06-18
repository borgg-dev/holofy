import { StyleSheet, View } from "react-native";

import { Text } from "@/components";
import type { Game } from "@/api";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";

type Props = {
  game: Game;
  size?: number;
};

// A game's section mark: a rounded chip in the game's brand accent carrying its initial.
// Deliberately generic — an original tint-and-letter badge, never the game's official
// logo. The accent is a theme brand-color *key*, so the chip resolves against the active
// scheme and reads in both light and dark. Decorative: the game name beside it carries
// the meaning for a screen reader.
export function GameGlyph({ game, size = 36 }: Props) {
  const theme = useTheme();
  const accent = theme.color[game.accent];

  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no"
      style={[
        styles.chip,
        {
          width: size,
          height: size,
          borderRadius: theme.radius.md,
          backgroundColor: withAlpha(accent, 0.16),
          borderColor: withAlpha(accent, 0.4),
        },
      ]}
    >
      <Text variant="titleMd" style={{ color: accent }}>
        {game.initial}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignItems: "center",
    justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth,
  },
});
