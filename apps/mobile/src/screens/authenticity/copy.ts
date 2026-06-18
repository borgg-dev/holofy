// Authenticity microcopy (master plan §6, charter §3.5). Product copy, not placeholder —
// this is the screen most exposed to defamation risk, so every line is deliberate: a private
// risk *signal*, never a fake/genuine verdict, never an accusation about a card or a seller.
// The localization seam (FR→ES→IT→DE→EN) swaps this file.

// ── Verdict ──────────────────────────────────────────────────────────────────

export const VERDICT_OVERLINE = "AUTHENTICITY SCREENING";
export const SIGNALS_HEADING = "What we looked at";
export const EVIDENCE_HEADING = "Evidence quality";

/** The "seek a professional" CTA shown above the value threshold — a prompt, never a verdict. */
export const ACTION_AUTHENTICATE = "Find a professional authenticator";
export const AUTHENTICATE_HINT =
  "Opens guidance on submitting this card to a professional authentication service.";
export const ACTION_RESCAN = "Re-screen with new shots";
export const ACTION_DONE = "Back to my card";

/** The reference-value line that makes the recommendation legible ("worth €X"). */
export function referenceValueLine(formattedValue: string): string {
  return `Worth ${formattedValue} — at this value, a professional opinion is worth the cost.`;
}

// The non-affiliation + scope line, persistent and never dismissible. Covers the grading/
// authentication services and the IP holders, and restates that this is decision support.
export const NON_AFFILIATION =
  "Not affiliated with PSA, CGC, BGS, or any authentication service, nor with Nintendo or The Pokémon Company.";

// ── Screening (loading) ────────────────────────────────────────────────────────

export const SCREENING_OVERLINE = "AUTHENTICITY SCREENING";
export const SCREENING_TITLE = "Reading the card's signals…";
export const SCREENING_SUB = "Print pattern, holo, font, cardstock, and the catalog cross-check.";

// ── Error ──────────────────────────────────────────────────────────────────────

export const ERROR_TITLE = "Couldn't complete the screening";
export const ERROR_SUB = "Nothing was charged. Give it another go.";
export const ERROR_RETRY = "Try again";

// ── Retake (capture too poor) ────────────────────────────────────────────────────

export const RETAKE_OVERLINE = "ONE MORE PASS";
export const RETAKE_TITLE = "Let's get clearer shots to screen";
export const RETAKE_SUB =
  "We won't flag a card on a capture we can't read. Fix these and the screening gets honest:";
export const RETAKE_ACTION = "Re-shoot for screening";
export const RETAKE_BACK = "Not now";

// ── Not assessed (below value threshold) ─────────────────────────────────────────

export const NOT_ASSESSED_OVERLINE = "NOT NEEDED HERE";
export const NOT_ASSESSED_TITLE = "Authenticity screening is for higher-value cards";
export const NOT_ASSESSED_SUB =
  "Counterfeiters target cards worth faking. This one sits below that line, so there's nothing to screen for — not a red flag, just not needed.";
export const NOT_ASSESSED_BACK = "Back to my card";

// ── Guided capture ───────────────────────────────────────────────────────────────

export const CAPTURE_TITLE = "Authenticity capture";

/** SR announcement when a shot locks and the flow advances. */
export function shotAdvanceAnnounce(label: string): string {
  return `${label} captured. Next shot.`;
}

export const CAPTURE_DONE_ANNOUNCE = "All shots captured. Screening.";
