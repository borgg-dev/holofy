import { useCallback, useEffect, useState } from "react";
import { AccessibilityInfo, ScrollView, StyleSheet, View } from "react-native";

import {
  Button,
  ConsentToggle,
  FoilSurface,
  IconButton,
  Screen,
  Skeleton,
  Text,
} from "@/components";
import { ChevronLeft } from "@/components/icons";
import { consentedTotal, useApi, type TrainingConsent } from "@/api";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import { CONSENT_COPY_VERSION, privacyCopy as copy } from "./copy";

type Props = { onBack?: () => void };

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; consent: TrainingConsent };

// The privacy / training-consent screen. A money-and-trust surface, so it reads Vault-calm:
// the explanation stated plainly in full, then one bespoke switch that lights the teal "lock"
// hue when on. The setting is its own thing — separate from agreeing to use the app — and OFF
// until the collector chooses it. Loading / error / save-error are all real states; a failed
// save rolls the toggle back rather than leaving it lying.
export function PrivacyScreen({ onBack }: Props) {
  const theme = useTheme();
  const api = useApi();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      setState({ status: "ready", consent: await api.trainingConsent() });
    } catch {
      setState({ status: "error" });
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const onToggle = useCallback(
    async (next: boolean) => {
      setSaving(true);
      setSaveError(false);
      try {
        const consent = await api.setTrainingConsent({
          granted: next,
          note: CONSENT_COPY_VERSION,
        });
        setState({ status: "ready", consent });
        AccessibilityInfo.announceForAccessibility(
          next ? "Sharing turned on" : "Sharing turned off"
        );
      } catch {
        // Never leave the UI asserting a state the server didn't accept.
        setSaveError(true);
      } finally {
        setSaving(false);
      }
    },
    [api]
  );

  return (
    <Screen ground="vault" padded>
      <Header onBack={onBack} />
      {state.status === "loading" ? (
        <LoadingBody />
      ) : state.status === "error" ? (
        <ErrorBody onRetry={() => void load()} />
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={{ paddingBottom: theme.space["10"] }}
        >
          <Explanation />
          <ControlCard
            consent={state.consent}
            saving={saving}
            saveError={saveError}
            onToggle={onToggle}
          />
        </ScrollView>
      )}
    </Screen>
  );
}

function Header({ onBack }: { onBack?: () => void }) {
  const theme = useTheme();
  return (
    <View style={[styles.header, { gap: theme.space["3"], marginBottom: theme.space["6"] }]}>
      {onBack ? (
        <IconButton accessibilityLabel="Back" onPress={onBack}>
          <ChevronLeft color={theme.color.textPrimary} />
        </IconButton>
      ) : null}
      <View style={{ gap: theme.space["1"] }}>
        <Text variant="overline" tone="tertiary">
          {copy.overline}
        </Text>
        <Text variant="titleLg" tone="primary">
          {copy.screenTitle}
        </Text>
      </View>
    </View>
  );
}

function Explanation() {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space["4"], marginBottom: theme.space["6"] }}>
      <Text variant="body" tone="secondary">
        {copy.what}
      </Text>
      <Text variant="body" tone="secondary">
        {copy.optional}
      </Text>
      <Text variant="body" tone="secondary">
        {copy.control}
      </Text>
      <Text variant="bodySm" tone="tertiary">
        {copy.separate}
      </Text>
    </View>
  );
}

function ControlCard({
  consent,
  saving,
  saveError,
  onToggle,
}: {
  consent: TrainingConsent;
  saving: boolean;
  saveError: boolean;
  onToggle: (next: boolean) => void;
}) {
  const theme = useTheme();
  const total = consentedTotal(consent);
  const status = !consent.granted
    ? copy.statusOff
    : total > 0
      ? copy.statusOnCount(total)
      : copy.statusOnNone;

  return (
    <FoilSurface level="elevated" foilEdge={consent.granted} padded>
      <View style={[styles.row, { gap: theme.space["4"] }]}>
        <Text variant="titleMd" tone="primary" style={styles.rowLabel}>
          {copy.toggleLabel}
        </Text>
        <ConsentToggle
          value={consent.granted}
          disabled={saving}
          onChange={onToggle}
          accessibilityLabel={consent.granted ? copy.toggleA11yOn : copy.toggleA11yOff}
        />
      </View>
      <Text
        variant="bodySm"
        tone={consent.granted ? "lock" : "tertiary"}
        style={{ marginTop: theme.space["3"] }}
      >
        {status}
      </Text>
      {saveError ? (
        <View
          style={[
            styles.saveError,
            {
              marginTop: theme.space["4"],
              backgroundColor: withAlpha(theme.color.errorRed, 0.12),
              borderRadius: theme.radius.md,
              padding: theme.space["3"],
            },
          ]}
        >
          <Text variant="bodySm" tone="primary">
            {copy.saveError}
          </Text>
        </View>
      ) : null}
    </FoilSurface>
  );
}

function LoadingBody() {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space["4"] }}>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} width="100%" height={18} radius={theme.radius.xs} />
      ))}
      <Skeleton width="100%" height={96} radius={theme.radius.lg} />
    </View>
  );
}

function ErrorBody({ onRetry }: { onRetry: () => void }) {
  const theme = useTheme();
  return (
    <View style={[styles.centered, { gap: theme.space["4"] }]}>
      <Text variant="bodySm" tone="secondary" style={styles.centeredText}>
        {copy.loadError}
      </Text>
      <Button label={copy.retry} tier="secondary" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center" },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  rowLabel: { flex: 1 },
  saveError: {},
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  centeredText: { textAlign: "center" },
});
