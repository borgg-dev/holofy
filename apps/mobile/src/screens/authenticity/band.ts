// The authenticity verdict's view-logic, kept pure so it's unit-tested without a renderer.
//
// Three hard rules from the defamation guardrail (charter §3.5, master plan §6) live here,
// in code rather than prose:
//   1. The screen never produces a fake/genuine verdict. The most adverse presentation is
//      "elevated risk — seek professional authentication". `bandPresentation` maps every
//      band to a non-accusatory headline; there is no "fake"/"counterfeit"/"genuine" string.
//   2. The verdict tone is teal (reassuring) or amber (caution) — never red. `elevatedRisk`
//      and `inconclusive` both read amber: a caution to seek a professional, not an alarm.
//   3. Evidence quality (the assessment's mean read-confidence) is NOT verdict-certainty and
//      is rendered separately — `evidenceQuality` describes how clearly the card was read,
//      never how sure we are that it's risky. The two never share a sentence.

import type {
  AuthenticityAssessment,
  AuthenticitySignal,
  RiskBand,
  SignalKind,
  SignalObservation,
} from "@/api";

/** Where the verdict tone lands. Teal reassures; amber cautions. Never red (charter §3.5). */
export type BandTone = "reassuring" | "caution";

export type BandPresentation = {
  tone: BandTone;
  /** The shield label — calm and non-accusatory. e.g. "No counterfeit indicators". */
  headline: string;
  /** The one-line read beneath the headline. Always hedged; never a guarantee or a verdict. */
  summary: string;
};

// The whole band→presentation table. `strongSignals` is the most reassuring we will say —
// "no counterfeit indicators", explicitly *not* "genuine". `elevatedRisk` is the most
// adverse — "some signals don't match", a recommendation to authenticate, never "fake".
const PRESENTATION: Record<RiskBand, BandPresentation> = {
  strongSignals: {
    tone: "reassuring",
    headline: "No counterfeit indicators",
    summary:
      "Every signal we could read lines up with our reference for this card. That's reassuring — but it's a screening signal, not a guarantee.",
  },
  inconclusive: {
    tone: "caution",
    headline: "We couldn't read enough to say",
    summary:
      "Some signals couldn't be read clearly, so this screening is inconclusive. For a card at this value, professional authentication is the safe call.",
  },
  elevatedRisk: {
    tone: "caution",
    headline: "Some signals don't match",
    summary:
      "A few signals diverge from our reference for this card. This isn't a verdict — we recommend professional authentication before you rely on it.",
  },
};

export function bandPresentation(band: RiskBand): BandPresentation {
  return PRESENTATION[band];
}

// ── Evidence quality (confidence) — kept strictly separate from the band ───────
//
// `confidence` on the assessment is the mean read-confidence of the signals: how clearly
// the card could be measured, not how certain the risk read is. We surface it as a quality
// label + a percent, in its own region, so it can never be misread as "X% sure it's risky".

export type EvidenceQuality = {
  /** A plain quality word — "Clear", "Partial", "Limited". Never a certainty. */
  label: string;
  /** The read-confidence as a whole percent, for the secondary line. */
  percent: number;
};

export function evidenceQuality(confidence: number): EvidenceQuality {
  const percent = Math.round(clamp01(confidence) * 100);
  const label = percent >= 80 ? "Clear" : percent >= 55 ? "Partial" : "Limited";
  return { label, percent };
}

/** The evidence-quality line — about the *read*, never the verdict (kept separate by design). */
export function evidenceQualityLine(quality: EvidenceQuality): string {
  return `${quality.label} read · we could read the card at ~${quality.percent}% clarity`;
}

// ── Per-signal reads ───────────────────────────────────────────────────────────

/** The reader-facing name for each signal, mirroring the breakdown in master plan §6. */
export const SIGNAL_LABEL: Record<SignalKind, string> = {
  print_pattern: "Print pattern",
  holo_signature: "Holo / foil",
  font_layout: "Font & layout",
  cardstock: "Cardstock",
  catalog_existence: "Catalog cross-check",
};

/** How each signal read presents. Tone mirrors the band rules: teal, amber, or neutral. */
export type SignalReadTone = "consistent" | "caution" | "unread";

export type SignalRead = {
  tone: SignalReadTone;
  /** A short state word shown beside the signal — paired with color, never color alone. */
  state: string;
};

// `deviation` is a caution, never "fake". `unreadable` is its own neutral state — it widens
// uncertainty rather than counting against the card, so it must not read as a strike.
const OBSERVATION_READ: Record<SignalObservation, SignalRead> = {
  consistent: { tone: "consistent", state: "Consistent" },
  inconclusive: { tone: "caution", state: "Inconclusive" },
  deviation: { tone: "caution", state: "Doesn't match" },
  unreadable: { tone: "unread", state: "Couldn't read" },
};

export function signalRead(signal: AuthenticitySignal): SignalRead {
  return OBSERVATION_READ[signal.observation];
}

// ── Accessibility ───────────────────────────────────────────────────────────────
//
// The screen reader must hear three things, separately and in order (master plan §6,
// charter §3.4): the band, the recommendation, and the evidence quality — the last never
// conflated with the verdict. `verdictA11y` reads exactly that, and nothing that asserts
// fake or genuine.

const RECOMMENDATION_PHRASE = "We recommend professional authentication";

export function verdictA11y(assessment: AuthenticityAssessment): string {
  const { headline, summary } = bandPresentation(assessment.band);
  const quality = evidenceQuality(assessment.confidence);
  const rec = assessment.recommendAuthentication ? ` ${RECOMMENDATION_PHRASE}.` : "";
  // Three regions, three sentences: verdict, recommendation, then evidence quality —
  // the quality framed as read clarity, deliberately apart from the verdict.
  return (
    `Authenticity screening: ${headline}. ${summary}${rec} ` +
    `Evidence quality, separately: a ${quality.label.toLowerCase()} read, ` +
    `we could read the card at about ${quality.percent} percent clarity.`
  );
}

/** "Print pattern: consistent. <detail>" — the per-signal SR line. */
export function signalA11y(signal: AuthenticitySignal): string {
  const name = SIGNAL_LABEL[signal.kind];
  const { state } = signalRead(signal);
  return `${name}: ${state.toLowerCase()}. ${signal.detail}`;
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}
