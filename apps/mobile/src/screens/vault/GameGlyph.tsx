import { StyleSheet, View } from "react-native";

import type { GameDisplay } from "@/api";
import { useTheme } from "@/theme";

type Props = {
  game: GameDisplay;
};

// A game section's mark: a slim rounded rail in the game's accent colour — a clean colour
// tag that identifies the game at a glance, without a fake letter avatar or the game's
// (IP-protected) logo. Decorative; the game name beside it carries the meaning for a
// screen reader.
export function GameGlyph({ game }: Props) {
  const theme = useTheme();
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no"
      style={[styles.rail, { backgroundColor: theme.color[game.accent] }]}
    />
  );
}

const styles = StyleSheet.create({
  rail: {
    width: 4,
    height: 38,
    borderRadius: 2,
  },
});
