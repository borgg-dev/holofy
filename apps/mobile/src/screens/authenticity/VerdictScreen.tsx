import { useEffect } from "react";
import { AccessibilityInfo, ScrollView, StyleSheet, View } from "react-native";

import type { AuthenticityAssessment } from "@/api";
import { Button, Screen, Text } from "@/components";
import { useTheme } from "@/theme";
import { withAlpha } from "@/theme/color";
import {
  bandPresentation,
  evidenceQuality,
  evidenceQualityLine,
  verdictA11y,
} from "./band";
import { ShieldMark } from "./ShieldMark";
import { SignalRow } from "./SignalRow";
import {
  ACTION_AUTHENTICATE,
  ACTION_DONE,
  ACTION_RESCAN,
  AUTHENTICATE_HINT,
  EVIDENCE_HEADING,
  NON_AFFILIATION,
  SIGNALS_HEADING,
  VERDICT_OVERLINE,
  referenceValueLine,
} from "./copy";

type Props = {
  assessment: AuthenticityAssessment;
  /** Above the value threshold, routes to professional-authentication guidance. */
  onAuthenticate?: () => void;
  /** Re-run the screening from a fresh capture. */
  onRescan?: () => void;
  onBack?: () => void;
};

// The authenticity verdict (master plan §6) — the bespoke Foil Vault shield moment. It
// renders an honest private read: a risk *band* shown as a teal (reassuring) or amber
// (caution) shield, never red and never a fake/genuine verdict. Beneath it sit the five
// per-signal reads, then — kept in its own region — the *evidence quality* (how clearly the
// card scanned), which is deliberately NOT the verdict's certainty. Above the value
// threshold the "seek a professional" CTA and the value that justifies it appear. The
// disclaimer is persistent, in the reading order, never fine print.
export function VerdictScreen({ assessment, onAuthenticate, onRescan, onBack }: Props) {
  const theme = useTheme();
  const { band, signals, confidence, recommendAuthentication, referenceValueEur, disclaimer } =
    assessment;
  const present = bandPresentation(band);
  const quality = evidenceQuality(confidence);
  const accent = present.tone === "reassuring" ? theme.color.vaultTeal : theme.color.amber;

  // Announce the band, the recommendation, and the evidence quality once — in that order,
  // the quality framed as read clarity so a SR user never hears it as verdict-certainty.
  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(verdictA11y(assessment));
  }, [assessment]);

  return (
    <Screen ground="vault" edges={["top", "bottom"]}>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { padding: theme.space["6"], paddingTop: theme.space["7"], gap: theme.space["7"] },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topbar}>
          <Text
            variant="label"
            tone="secondary"
            onPress={onBack}
            accessibilityRole="button"
            accessibilityLabel="Back"
          >
            ‹ Back
          </Text>
        </View>

        {/* Shield header — the signature moment. The shield is decorative; the headline
            + summary carry the verdict, so the SR user gets the real content as text. */}
        <View style={[styles.shieldBlock, { gap: theme.space["5"] }]}>
          <ShieldMark tone={present.tone} />
          <View style={[styles.shieldText, { gap: theme.space["2"] }]} accessibilityRole="header">
            <Text variant="overline" tone="tertiary">
              {VERDICT_OVERLINE}
            </Text>
            <Text variant="displayMd" style={{ color: accent }}>
              {present.headline}
            </Text>
            <Text variant="bodySm" tone="secondary" style={styles.summary}>
              {present.summary}
            </Text>
          </View>
        </View>

        {/* The "seek a professional" recommendation — a prompt above the value threshold,
            with the value that makes it legible. Never a verdict. */}
        {recommendAuthentication ? (
          <RecommendationCard
            valueEur={referenceValueEur}
            onAuthenticate={onAuthenticate}
            accent={accent}
          />
        ) : null}

        {/* Per-signal breakdown. */}
        <View style={{ gap: theme.space["5"] }}>
          <Text variant="overline" tone="tertiary">
            {SIGNALS_HEADING}
          </Text>
          <View style={{ gap: theme.space["6"] }}>
            {signals.map((signal) => (
              <SignalRow key={signal.kind} signal={signal} />
            ))}
          </View>
        </View>

        {/* Evidence quality — its own region, explicitly about the *read*, not the verdict.
            This is the F2 separation: confidence is measurement clarity, kept apart. */}
        <View
          style={[
            styles.evidence,
            {
              backgroundColor: theme.color.bgRaised,
              borderRadius: theme.radius.md,
              padding: theme.space["5"],
              gap: theme.space["3"],
            },
          ]}
          accessibilityRole="text"
          accessibilityLabel={`Evidence quality, separate from the result: ${evidenceQualityLine(
            quality
          )}`}
        >
          <Text variant="overline" tone="tertiary">
            {EVIDENCE_HEADING}
          </Text>
          <EvidenceMeter percent={quality.percent} />
          <Text variant="caption" tone="tertiary" tabular style={styles.evidenceLine}>
            {evidenceQualityLine(quality)}
          </Text>
        </View>

        {/* Actions. */}
        <View style={{ gap: theme.space["3"] }}>
          <Button label={ACTION_RESCAN} tier="secondary" onPress={onRescan} />
          <Button label={ACTION_DONE} tier="tertiary" onPress={onBack} />
        </View>

        {/* Disclaimer — persistent, never dismissible, in the reading order. */}
        <Text
          variant="caption"
          tone="tertiary"
          style={[
            styles.disclaimer,
            { borderTopColor: theme.color.border, paddingTop: theme.space["5"] },
          ]}
        >
          {`${disclaimer} ${NON_AFFILIATION}`}
        </Text>
      </ScrollView>
    </Screen>
  );
}

// The recommendation, on an accent-ruled card — a calm prompt to seek a professional, with
// the card's value so the advice is legible ("worth €X, worth a professional opinion").
function RecommendationCard({
  valueEur,
  onAuthenticate,
  accent,
}: {
  valueEur: number | null;
  onAuthenticate?: () => void;
  accent: string;
}) {
  const theme = useTheme();
  const valueLine = valueEur != null ? referenceValueLine(formatEur(valueEur)) : null;
  return (
    <View
      style={[
        styles.recommend,
        {
          backgroundColor: withAlpha(accent, 0.08),
          borderLeftColor: accent,
          borderRadius: theme.radius.sm,
          paddingVertical: theme.space["5"],
          paddingHorizontal: theme.space["5"],
          gap: theme.space["4"],
        },
      ]}
    >
      {valueLine ? (
        <Text variant="bodySm" tone="secondary" tabular>
          {valueLine}
        </Text>
      ) : null}
      <Button
        label={ACTION_AUTHENTICATE}
        tier="primary"
        onPress={onAuthenticate}
        accessibilityHint={AUTHENTICATE_HINT}
      />
    </View>
  );
}

// The evidence-quality meter — a thin bar reading how clearly the card scanned, in a neutral
// accent so it never reads as a risk score. It measures the *read*, not the verdict.
function EvidenceMeter({ percent }: { percent: number }) {
  const theme = useTheme();
  return (
    <View
      style={[styles.meter, { backgroundColor: theme.color.bgInset, borderRadius: theme.radius.pill }]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      <View
        style={[
          styles.meterFill,
          {
            width: `${Math.max(0, Math.min(100, percent))}%`,
            backgroundColor: theme.color.textSecondary,
            borderRadius: theme.radius.pill,
          },
        ]}
      />
    </View>
  );
}

/** € in the German convention (€1.234,56) — matches the reveal screen's currency rendering. */
function formatEur(value: number): string {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(value);
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
  },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
  },
  shieldBlock: {
    alignItems: "flex-start",
  },
  shieldText: {
    alignSelf: "stretch",
  },
  summary: {
    lineHeight: 20,
  },
  recommend: {
    borderLeftWidth: 3,
  },
  evidence: {
    alignSelf: "stretch",
  },
  evidenceLine: {
    lineHeight: 18,
  },
  meter: {
    height: 6,
    overflow: "hidden",
  },
  meterFill: {
    height: "100%",
  },
  disclaimer: {
    borderTopWidth: 1,
  },
});
