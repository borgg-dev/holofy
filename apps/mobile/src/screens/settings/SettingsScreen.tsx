import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { AppearanceToggle, Button, FoilSurface, Screen, Text } from "@/components";
import { ChevronRight } from "@/components/icons";
import { useOptionalAuth } from "@/auth/AuthContext";
import { useTheme, useThemeMode } from "@/theme";
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
  // Present only in live mode (no AuthProvider in the demo) — drives the real account header
  // and the sign-out action.
  const auth = useOptionalAuth();

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
        <AccountCard email={auth?.user?.email ?? null} />

        <AppearanceSection />

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

        {auth ? (
          <Button
            label="Sign out"
            tier="secondary"
            onPress={() => void auth.signOut()}
            style={{ marginTop: theme.space["2"] }}
          />
        ) : null}

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

// The appearance control. A labeled segmented toggle that switches the whole app between
// following the device and a pinned light/dark scheme — the choice persists across restarts.
// Sits on the quiet inset surface so the violet active segment is the only colour that lifts.
function AppearanceSection() {
  const theme = useTheme();
  const { mode, setThemeMode } = useThemeMode();
  return (
    <View style={{ gap: theme.space["3"] }}>
      <Text variant="overline" tone="tertiary">
        {copy.appearanceOverline}
      </Text>
      <AppearanceToggle value={mode} onChange={setThemeMode} />
      <Text variant="caption" tone="tertiary">
        {copy.appearanceHint}
      </Text>
    </View>
  );
}

// The identity block. A foil-edged avatar disc with the collector's initial, name, and plan
// status — the warmest surface on an otherwise calm screen.
function AccountCard({ email }: { email: string | null }) {
  const theme = useTheme();
  // The real signed-in email in live mode; the demo placeholder name otherwise.
  const displayName = email ?? copy.accountName;
  const initial = displayName.charAt(0).toUpperCase();
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
            {initial}
          </Text>
        </View>
        <View style={{ flex: 1, gap: theme.space["1"] }}>
          <Text variant="titleMd" tone="primary" numberOfLines={1}>
            {displayName}
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
