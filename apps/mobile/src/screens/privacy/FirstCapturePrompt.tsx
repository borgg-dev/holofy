import { StyleSheet, View } from "react-native";

import { Button, FoilSurface, Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { firstCapturePrompt as copy } from "./copy";

type Props = {
  /** Opt in. The affirmative action — never the default. */
  onAccept: () => void;
  /** Decline. Off is the default, so this is the no-op path. */
  onDecline: () => void;
};

// A one-time, plainly-worded offer shown once after a collector's first scan, so the consent
// ask lands in context (they just saw the app work) rather than buried in onboarding. Consent
// is a real choice, so the two buttons are visual peers — both the same secondary tier, no
// pre-selected yes and no fill steering the eye toward opting in (charter §3.5). Lives as a
// card on the Vault ground; the caller renders it over the reveal once.
export function FirstCapturePrompt({ onAccept, onDecline }: Props) {
  const theme = useTheme();
  return (
    <View
      style={[styles.root, { padding: theme.space["5"], backgroundColor: withAlpha(theme.color.bg, 0.82) }]}
    >
      <FoilSurface level="elevated" foilEdge padded>
        <View style={{ gap: theme.space["3"] }}>
          <Text variant="overline" tone="tertiary">
            {copy.overline}
          </Text>
          <Text variant="titleLg" tone="primary">
            {copy.title}
          </Text>
          <Text variant="body" tone="secondary">
            {copy.body}
          </Text>
        </View>
        <View style={[styles.actions, { gap: theme.space["3"], marginTop: theme.space["6"] }]}>
          <Button
            label={copy.accept}
            tier="secondary"
            onPress={onAccept}
            accessibilityHint={copy.acceptA11y}
          />
          <Button
            label={copy.decline}
            tier="secondary"
            onPress={onDecline}
            accessibilityHint={copy.declineA11y}
          />
        </View>
      </FoilSurface>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { ...StyleSheet.absoluteFillObject, justifyContent: "center" },
  actions: {},
});
