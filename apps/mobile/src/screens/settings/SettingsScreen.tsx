import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { FoilSurface, Screen, Text } from "@/components";
import { ChevronRight } from "@/components/icons";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { settingsCopy as copy } from "./copy";

type Props = {
  /** Open the privacy / training-consent screen (a stack route over the tabs). */
  onPrivacy?: () => void;
};

// The Settings tab. A calm account header — the signed-in collector, their plan — over a small
// set of bespoke rows. Account/plan are honest placeholders for the Phase-1 auth identity, not
// faked data; Privacy routes to the real consent screen. The non-affiliation legal line sits at
// the foot. A money-and-trust surface, so it reads Vault-calm: no stock list chrome.
export function SettingsScreen({ onPrivacy }: Props) {
  const theme = useTheme();

  return (
    <Screen ground="vault" edges={["top"]} padded>
      <View style={{ gap: theme.space["1"], marginBottom: theme.space["6"] }}>
        <Text variant="overline" tone="tertiary">
          {copy.overline}
        </Text>
        <Text variant="titleLg" tone="primary">
          {copy.title}
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: theme.space["10"], gap: theme.space["4"] }}
      >
        <AccountCard />

        <View style={{ gap: theme.space["3"] }}>
          <SettingRow
            label={copy.planRowLabel}
            value={copy.planRowValue}
            hint={copy.planRowHint}
          />
          <SettingRow
            label={copy.privacyRowLabel}
            value={copy.privacyRowValue}
            onPress={onPrivacy}
          />
        </View>

        <Text
          variant="caption"
          tone="tertiary"
          style={{ marginTop: theme.space["3"], lineHeight: 18 }}
        >
          {copy.legal}
        </Text>
      </ScrollView>
    </Screen>
  );
}

// The identity block. A foil-edged avatar disc with the collector's initial, name, and plan
// status — the warmest surface on an otherwise calm screen.
function AccountCard() {
  const theme = useTheme();
  return (
    <FoilSurface level="elevated" foilEdge padded>
      <View style={[styles.account, { gap: theme.space["4"] }]}>
        <View
          style={[
            styles.avatar,
            {
              backgroundColor: withAlpha(theme.color.holoViolet, 0.18),
              borderColor: withAlpha(theme.color.holoViolet, 0.45),
            },
          ]}
        >
          <Text variant="titleLg" tone="accent">
            {copy.accountName.charAt(0)}
          </Text>
        </View>
        <View style={{ flex: 1, gap: theme.space["1"] }}>
          <Text variant="titleMd" tone="primary">
            {copy.accountName}
          </Text>
          <Text variant="caption" tone="tertiary">
            {copy.accountStatus}
          </Text>
        </View>
      </View>
    </FoilSurface>
  );
}

// A single settings row. Tappable rows carry a chevron and a press wash; static rows (plan,
// for now) show their value plus a quiet hint and never look falsely interactive.
function SettingRow({
  label,
  value,
  hint,
  onPress,
}: {
  label: string;
  value: string;
  hint?: string;
  onPress?: () => void;
}) {
  const theme = useTheme();
  const interactive = onPress != null;

  const body = (
    <View style={[styles.row, { padding: theme.space["5"], gap: theme.space["3"] }]}>
      <View style={{ flex: 1, gap: theme.space["1"] }}>
        <Text variant="titleMd" tone="primary">
          {label}
        </Text>
        <Text variant="caption" tone="secondary">
          {value}
        </Text>
        {hint ? (
          <Text variant="caption" tone="tertiary">
            {hint}
          </Text>
        ) : null}
      </View>
      {interactive ? <ChevronRight color={theme.color.textTertiary} /> : null}
    </View>
  );

  if (!interactive) {
    return <FoilSurface level="raised" padded={false}>{body}</FoilSurface>;
  }

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}. ${value}`}
      style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
    >
      <FoilSurface level="raised" padded={false}>
        {body}
      </FoilSurface>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  account: { flexDirection: "row", alignItems: "center" },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: "center",
    justifyContent: "center",
  },
  row: { flexDirection: "row", alignItems: "center" },
});
