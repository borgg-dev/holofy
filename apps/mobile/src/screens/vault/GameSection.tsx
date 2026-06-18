import { useEffect, useState, type ReactNode } from "react";
import {
  AccessibilityInfo,
  LayoutAnimation,
  Platform,
  Pressable,
  StyleSheet,
  UIManager,
  View,
} from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { Text, ValueText } from "@/components";
import { ChevronRight } from "@/components/icons";
import type { GameGroup } from "@/api";
import { useReduceMotion, useTheme } from "@/theme";
import { GameGlyph } from "./GameGlyph";

type Props = {
  group: GameGroup;
  /** The holding rows for this game — rendered when expanded. */
  children: ReactNode;
};

// Android opts out of LayoutAnimation by default; the height collapse here relies on it.
if (Platform.OS === "android" && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// One game's holdings under a collapsible header — the Vault's single grouping level.
// The header is the tap target: the generic glyph, the nominative game name, and a
// right-aligned "N cards · €subtotal". Tapping toggles the body; the chevron rotates to
// point down when open. Reduced motion skips the height/rotation tweens and snaps.
export function GameSection({ group, children }: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const [open, setOpen] = useState(true);

  const { game, cardCount, subtotal } = group;
  const accent = theme.color[game.accent];

  const spin = useSharedValue(1);
  useEffect(() => {
    const to = open ? 1 : 0;
    spin.value = reduceMotion
      ? to
      : withTiming(to, {
          duration: theme.motion.duration.base,
          easing: Easing.bezier(0.2, 0, 0, 1),
        });
  }, [open, reduceMotion, spin, theme.motion.duration.base]);

  const chevronStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${spin.value * 90}deg` }],
  }));

  const toggle = () => {
    if (!reduceMotion) {
      LayoutAnimation.configureNext(
        LayoutAnimation.create(
          theme.motion.duration.base,
          LayoutAnimation.Types.easeInEaseOut,
          LayoutAnimation.Properties.opacity
        )
      );
    }
    setOpen((v) => !v);
    AccessibilityInfo.announceForAccessibility(
      `${game.name}, ${open ? "collapsed" : "expanded"}`
    );
  };

  const countLabel = `${cardCount} ${cardCount === 1 ? "card" : "cards"}`;

  return (
    <View>
      <Pressable
        onPress={toggle}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${game.name}, ${countLabel}`}
        accessibilityHint={open ? "Collapses this game's cards." : "Expands this game's cards."}
        style={({ pressed }) => [styles.header, { opacity: pressed ? 0.8 : 1, gap: theme.space["4"] }]}
      >
        <GameGlyph game={game} />
        <View style={styles.headerText}>
          <Text variant="titleMd" tone="primary" numberOfLines={1}>
            {game.name}
          </Text>
          <View style={[styles.subtotal, { gap: theme.space["2"] }]}>
            <Text variant="caption" tone="tertiary">
              {countLabel} ·
            </Text>
            <ValueText amount={subtotal} variant="body" style={{ color: accent }} />
          </View>
        </View>
        <Animated.View style={chevronStyle}>
          <ChevronRight color={theme.color.textTertiary} />
        </Animated.View>
      </Pressable>

      {open ? (
        <View style={{ gap: theme.space["3"], marginTop: theme.space["4"] }}>{children}</View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerText: { flex: 1 },
  subtotal: { flexDirection: "row", alignItems: "center" },
});
