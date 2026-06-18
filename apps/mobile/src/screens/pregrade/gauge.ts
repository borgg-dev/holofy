// The gauge's view-logic, kept pure so it's unit-tested without a renderer.
//
// Two hard rules from the honest-framing gate (charter §3.1, gauge spec §3) live here,
// in code rather than prose: this module never produces a single absolute grade — only a
// band and a probability — and the verdict color is never red, only teal / amber / neutral.

import type { GradeProbabilityRange, SubScore } from "@/api";

/** Where the recommendation lands. Color is paired with words; `hold` is neutral, never red. */
export type VerdictTone = "worth" | "borderline" | "hold";

export type Verdict = {
  tone: VerdictTone;
  /** The recommendation phrase, e.g. "Worth grading". Always shown beside the band. */
  label: string;
};

// The submission decision is driven by P(grade ≥ floor), not the band midpoint — a wide
// "8–10" with low confidence shouldn't read as confidently as a tight "9–9". These
// thresholds are the product's risk posture for "is this worth a ~€20 submission fee".
const WORTH_AT_LEAST_P = 0.6;
const BORDERLINE_AT_LEAST_P = 0.35;

export function verdictFor(range: GradeProbabilityRange): Verdict {
  if (range.pAtLeast >= WORTH_AT_LEAST_P) return { tone: "worth", label: "Worth grading" };
  if (range.pAtLeast >= BORDERLINE_AT_LEAST_P) return { tone: "borderline", label: "Borderline" };
  return { tone: "hold", label: "Hold off for now" };
}

/** The band as a display string, e.g. "8–9" or "8" when the floor and ceiling coincide. */
export function rangeLabel(range: GradeProbabilityRange): string {
  return range.likelyLow === range.likelyHigh
    ? String(range.likelyLow)
    : `${range.likelyLow}–${range.likelyHigh}`;
}

/** The headline verdict line, e.g. "Likely 8–9 · Worth grading". Never a lone number. */
export function verdictLine(range: GradeProbabilityRange, verdict: Verdict): string {
  return `Likely ${rangeLabel(range)} · ${verdict.label}`;
}

/** Round a 0–1 confidence to a whole percent for the "~85% within ±1 grade" line. */
export function confidencePercent(confidence: number): number {
  return Math.round(clamp01(confidence) * 100);
}

// ── Arc geometry ─────────────────────────────────────────────────────────────
//
// A 200° arc spans grades 1→10 (gauge spec §2). The SVG matches the demo's viewBox so
// the band lands identically to the reference: center (120,120), radius 94, sweeping from
// 170° round to -10° (200° total, opening at the bottom). Grade g maps to its fraction
// along that sweep; a band paints the arc between two grades.

export const GAUGE = {
  viewBox: { width: 240, height: 140 },
  center: { x: 120, y: 120 },
  radius: 94,
  // A 200° sweep centered on the top (90°): grade 1 at 190° (lower-left), grade 10 at
  // -10° (lower-right), so the two ends sit level and the arc opens at the bottom.
  startDeg: 190,
  endDeg: -10,
  minGrade: 1,
  maxGrade: 10,
} as const;

/** 0 at grade 1, 1 at grade 10. Clamped so an out-of-range value can't paint off-arc. */
export function gradeFraction(grade: number): number {
  const { minGrade, maxGrade } = GAUGE;
  return clamp01((grade - minGrade) / (maxGrade - minGrade));
}

/** A point on the arc at a 0–1 fraction along the sweep. */
export function pointAtFraction(fraction: number): { x: number; y: number } {
  const f = clamp01(fraction);
  const deg = GAUGE.startDeg + (GAUGE.endDeg - GAUGE.startDeg) * f;
  const rad = (deg * Math.PI) / 180;
  return {
    x: GAUGE.center.x + Math.cos(rad) * GAUGE.radius,
    y: GAUGE.center.y - Math.sin(rad) * GAUGE.radius,
  };
}

/** An SVG arc path between two grades, used for both the full track and the predicted band. */
export function arcPath(fromGrade: number, toGrade: number): string {
  const from = pointAtFraction(gradeFraction(fromGrade));
  const to = pointAtFraction(gradeFraction(toGrade));
  const sweepDeg =
    Math.abs(GAUGE.endDeg - GAUGE.startDeg) *
    Math.abs(gradeFraction(toGrade) - gradeFraction(fromGrade));
  const largeArc = sweepDeg > 180 ? 1 : 0;
  // Clockwise (sweep-flag 1): grades increase left→right round the top, matching the spec.
  return `M ${round(from.x)} ${round(from.y)} A ${GAUGE.radius} ${GAUGE.radius} 0 ${largeArc} 1 ${round(to.x)} ${round(to.y)}`;
}

/** The modal grade the band's bright core sits at — the band's midpoint. */
export function modalGrade(range: GradeProbabilityRange): number {
  return (range.likelyLow + range.likelyHigh) / 2;
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

// ── Accessibility ────────────────────────────────────────────────────────────

const AXIS_NOUN: Record<SubScore["axis"], string> = {
  centering: "Centering",
  corners: "Corners",
  edges: "Edges",
  surface: "Surface",
};

const PROVENANCE_PHRASE: Record<SubScore["provenance"], string> = {
  measured: "measured",
  estimated: "estimated",
  limited: "limited assessment",
};

/** "Centering: 9 out of 10, measured." — value, max, and provenance, per spec §62. */
export function subScoreA11y(sub: SubScore): string {
  const noun = AXIS_NOUN[sub.axis];
  if (sub.provenance === "limited") {
    return `${noun}: limited assessment, around ${formatScore(sub.score)} out of 10.`;
  }
  return `${noun}: ${formatScore(sub.score)} out of 10, ${PROVENANCE_PHRASE[sub.provenance]}.`;
}

/**
 * The whole-screen SR summary, per spec §61 — reads the range, the verdict, and the
 * confidence, never a single grade.
 */
export function gaugeA11y(
  range: GradeProbabilityRange,
  verdict: Verdict,
  confidence: number
): string {
  const band =
    range.likelyLow === range.likelyHigh
      ? `likely ${range.likelyLow}`
      : `likely ${range.likelyLow} to ${range.likelyHigh}`;
  return `Pre-grade estimate: ${band}. ${verdict.label}. Confidence: about ${confidencePercent(
    confidence
  )} percent within one grade.`;
}

/** A score rendered for display/SR — one decimal, trimmed when whole ("9" not "9.0"). */
export function formatScore(score: number): string {
  const rounded = Math.round(score * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/** A sub-score's display value, e.g. "9.0 / 10", or "~7 / 10" when the axis is limited. */
export function subScoreValue(sub: SubScore): string {
  const lead = sub.provenance === "limited" ? "~" : "";
  return `${lead}${formatScore(sub.score)} / 10`;
}
