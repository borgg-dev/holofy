import { useEffect, useState } from "react";
import { Image, StyleSheet, View } from "react-native";
import Animated, {
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";

import { useReduceMotion, useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { Text } from "./Text";

type FoilCardProps = {
  /** Width as a fraction of the parent — spec calls for ~64% of viewport. */
  widthPct?: number;
  /** The card's name/set, shown on the placeholder face when there's no real artwork. */
  title: string;
  subtitle: string;
  /** A11y description of the captured card. */
  accessibilityLabel: string;
  /** Run the once-only reveal sweep on mount. Off → render at settled rest. */
  reveal?: boolean;
  /** The real catalog artwork to render as the card face. When set (and it loads) the foil
   *  sweep layers over the actual card; when null/failed, the placeholder face is shown. */
  imageUrl?: string | null;
};

// The foil card hero (foil-reveal.md). A near-black Vault card face in the trading-card
// ratio, tilted into a subtle 3D resting pose, with the brand foil sweep layered over it
// at low opacity. On reveal the sweep brightens and travels once (0.55→0.18 peak→rest);
// a specular sheen passes left→right. At rest it holds the settled 0.18 shimmer. Reduced
// motion renders the settled state immediately — no sweep, no sheen, no scale-in.
//
// react-native-svg has no conic gradient, so the signature conic sweep is approximated as
// stacked angled linear bands through the three brand hues — the same read at card scale.
export function FoilCard({
  widthPct = 0.64,
  title,
  subtitle,
  accessibilityLabel,
  reveal = true,
  imageUrl = null,
}: FoilCardProps) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();

  // Show the real artwork when we have a URL that loads; on a load failure fall back to the
  // placeholder face so a missing/broken image never leaves a blank hero.
  const [artFailed, setArtFailed] = useState(false);
  const showArt = !!imageUrl && !artFailed;

  // 0 = pre-reveal, 1 = settled. Drives entrance scale/opacity + foil brightness.
  const progress = useSharedValue(reveal && !reduceMotion ? 0 : 1);
  // Travels the specular sheen across the face, once.
  const sheen = useSharedValue(reveal && !reduceMotion ? 0 : 1);

  useEffect(() => {
    if (!reveal || reduceMotion) {
      progress.value = 1;
      sheen.value = 1;
      return;
    }
    progress.value = withTiming(1, {
      duration: theme.motion.duration.reveal,
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    });
    sheen.value = withDelay(
      theme.motion.duration.fast,
      withTiming(1, { duration: theme.motion.duration.slow * 2, easing: Easing.bezier(0.2, 0, 0, 1) })
    );
  }, [reveal, reduceMotion, progress, sheen, theme.motion.duration]);

  const cardStyle = useAnimatedStyle(() => ({
    opacity: interpolate(progress.value, [0, 1], [0, 1]),
    transform: [
      { perspective: 900 },
      { translateY: interpolate(progress.value, [0, 1], [16, 0]) },
      { scale: interpolate(progress.value, [0, 1], [0.92, 1]) },
      // The resting 3D pose: rotateX 6°, rotateY -8° (spec). Eased in with the entrance.
      { rotateX: `${interpolate(progress.value, [0, 1], [0, 6])}deg` },
      { rotateY: `${interpolate(progress.value, [0, 1], [0, -8])}deg` },
    ],
  }));

  // Foil opacity blooms then settles (peak at the reveal midpoint). Over real artwork the
  // sweep is dialed back so it reads as a holo *sheen* on the card rather than tinting it; the
  // placeholder face keeps the fuller bloom since there's nothing under it to obscure.
  const foilStyle = useAnimatedStyle(() => ({
    opacity: showArt
      ? interpolate(progress.value, [0, 0.5, 1], [0.14, 0.3, 0.1])
      : interpolate(progress.value, [0, 0.5, 1], [0.22, 0.5, 0.18]),
  }));

  const sheenStyle = useAnimatedStyle(() => ({
    opacity: interpolate(sheen.value, [0, 0.5, 1], [0, 0.5, 0]),
    transform: [{ translateX: interpolate(sheen.value, [0, 1], [-1, 1]) * 220 }, { rotate: "16deg" }],
  }));

  return (
    <Animated.View
      accessibilityRole="image"
      accessibilityLabel={accessibilityLabel}
      style={[
        styles.card,
        {
          width: `${widthPct * 100}%`,
          aspectRatio: theme.cardRatio,
          borderRadius: theme.radius.card,
          backgroundColor: theme.color.bgInset,
          borderColor: withAlpha(theme.color.holoViolet, 0.4),
          ...cardShadow,
        },
        cardStyle,
      ]}
    >
      {/* The real card artwork, full-bleed under the foil layers so the shimmer reads as a
          holo sheen over the actual card. Falls back to the placeholder face on load error. */}
      {showArt ? (
        <Image
          source={{ uri: imageUrl! }}
          style={StyleSheet.absoluteFill}
          resizeMode="cover"
          onError={() => setArtFailed(true)}
          accessibilityIgnoresInvertColors
        />
      ) : null}

      {/* The conic-approximating foil sweep, masked to the card. */}
      <Animated.View style={[StyleSheet.absoluteFill, foilStyle]} pointerEvents="none">
        <FoilSweep />
      </Animated.View>

      {/* Traveling specular highlight (foilSheen). */}
      <Animated.View
        pointerEvents="none"
        style={[styles.sheen, { backgroundColor: withAlpha(theme.color.textPrimary, 0.55) }, sheenStyle]}
      />

      {/* Placeholder face — only when there's no real artwork to show. Hidden from the reader
          since the card's identity is announced by the parent's label. */}
      {showArt ? null : (
        <View style={styles.face} importantForAccessibility="no-hide-descendants">
          <View style={[styles.facePlate, { borderColor: withAlpha(theme.color.textPrimary, 0.08) }]} />
          <Text variant="titleLg" tone="primary" style={styles.faceTitle}>
            {title}
          </Text>
          <Text variant="caption" tone="secondary">
            {subtitle}
          </Text>
        </View>
      )}
    </Animated.View>
  );
}

// Stacked angled bands through holoViolet → vaultTeal → foilMagenta → back, the brand
// conic sweep flattened to a diagonal. Rendered once in SVG; the parent animates its
// opacity for the reveal bloom. Blend isn't available in RN, so opacity + the violet
// border carry the "lit foil" read over the near-black face.
function FoilSweep() {
  const theme = useTheme();
  return (
    <Svg width="100%" height="100%">
      <Defs>
        <LinearGradient id="foilSweep" x1="0%" y1="0%" x2="100%" y2="100%">
          <Stop offset="0%" stopColor={theme.color.holoViolet} />
          <Stop offset="28%" stopColor={theme.color.vaultTeal} />
          <Stop offset="52%" stopColor={theme.color.foilMagenta} />
          <Stop offset="74%" stopColor={theme.color.holoViolet} />
          <Stop offset="100%" stopColor={theme.color.vaultTeal} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100%" height="100%" fill="url(#foilSweep)" />
    </Svg>
  );
}

const cardShadow = {
  // elevation.foil — the lifted, lit glow under a revealed foil card.
  shadowColor: "#6C3CE0",
  shadowOpacity: 0.35,
  shadowRadius: 50,
  shadowOffset: { width: 0, height: 18 },
  elevation: 16,
};

const styles = StyleSheet.create({
  card: {
    borderWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
    alignSelf: "center",
  },
  sheen: {
    position: "absolute",
    top: -40,
    bottom: -40,
    width: 80,
    left: "40%",
  },
  face: {
    flex: 1,
    padding: 18,
    justifyContent: "flex-end",
    gap: 2,
  },
  facePlate: {
    ...StyleSheet.absoluteFillObject,
    margin: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 10,
  },
  faceTitle: {
    marginBottom: 2,
  },
});
