// Pre-grade microcopy (gauge spec: packages/design-tokens/screens/pre-grade-gauge.md).
// Product copy, not placeholder — this is the trust screen, so every line is deliberate
// and disclaimed. The localization seam (FR→ES→IT→DE→EN) swaps this file.

import type { SubScore } from "@/api";

// ── Gauge ────────────────────────────────────────────────────────────────────

export const GAUGE_OVERLINE = "PRE-GRADE ESTIMATE";
export const GAUGE_MODAL_LABEL = "modal";

/** The confidence line under the gauge. The percent comes from the assessment. */
export function confidenceLine(percent: number): string {
  return `Confidence ~${percent}% within ±1 grade`;
}

export const SUBSCORES_HEADING = "What we looked at";

export const AXIS_LABEL: Record<SubScore["axis"], string> = {
  centering: "Centering",
  corners: "Corners",
  edges: "Edges",
  surface: "Surface",
};

export const PROVENANCE_TAG: Record<SubScore["provenance"], string> = {
  measured: "Measured",
  estimated: "Estimated",
  limited: "Limited",
};

/** Shown inline when an axis (typically surface) couldn't be fully read. */
export const SURFACE_CAVEAT =
  "Surface limited — we couldn't fully read the holo under raking light, so we widened the range to reflect it.";

// The disclaimer is two sentences and never dismissible (spec §15, §28). The first is the
// honest framing; the second is the non-affiliation line covering grading services and IP.
export const NON_AFFILIATION =
  "Not affiliated with PSA, CGC, BGS, or any grading service, nor with Nintendo or The Pokémon Company. Final grades may differ.";

export const ACTION_LOG_GRADE = "Log my real grade later";
export const ACTION_WHAT_AFFECTS = "See what affects this";

// Staged, honest copy for the assessment — names what's happening, no fake progress bar.
export const COMPUTING_OVERLINE = "PRE-GRADE ESTIMATE";
export const COMPUTING_TITLE = "Assessing four factors…";
export const COMPUTING_SUB = "Centering, corners, edges, and surface from your angles.";

// ── Error ────────────────────────────────────────────────────────────────────

export const ERROR_TITLE = "Couldn't complete the assessment";
export const ERROR_SUB = "Nothing was charged. Give it another go.";
export const ERROR_RETRY = "Try again";

// ── Retake ───────────────────────────────────────────────────────────────────

export const RETAKE_OVERLINE = "ONE MORE PASS";
export const RETAKE_TITLE = "Let's get a cleaner multi-angle scan";
export const RETAKE_SUB =
  "We won't put a number on a shot we can't read well. Fix these and the estimate gets honest:";
export const RETAKE_ACTION = "Re-scan for grading";
export const RETAKE_BACK = "Not now";

// ── Guided multi-angle capture ───────────────────────────────────────────────

export const CAPTURE_BACK = "‹ Back";

/** The capture is a sequence of angles; the spec calls for multiple for surface (raking). */
export const CAPTURE_TITLE = "Grade-quality capture";

/** SR announcement when an angle locks and advances. */
export function angleAdvanceAnnounce(label: string): string {
  return `${label} captured. Next angle.`;
}

export const CAPTURE_DONE_ANNOUNCE = "All angles captured. Assessing.";
