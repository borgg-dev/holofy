// Foil-reveal microcopy (foil-reveal.md). Product copy, not placeholder — this is the
// most brand-defining screen, so the lines are deliberate. The localization seam
// (FR→ES→IT→DE→EN) swaps this file.

export const EYEBROW_PRICE = "MARKET VALUE · CARDMARKET";
export const EYEBROW_FETCHING = "FETCHING CARDMARKET PRICE";
export const EYEBROW_NO_PRICE = "MARKET VALUE";

/** No liquid € comp — never a fabricated number. */
export const NO_PRICE_TITLE = "No recent € sales";
export const NO_PRICE_SUB = "We'll alert you when one lists.";

export const ACTION_ADD = "Add to Vault";
export const ACTION_ADDED = "Added to Vault";
export const ACTION_GRADE = "Pre-grade this card";
export const ACTION_AUTH = "Check authenticity";

export const ADD_HINT = "Saves this card to your collection and updates your Vault value.";
export const GRADE_HINT = "Opens the guided multi-angle capture to estimate a grade.";

/** Trend line tail; the leading percent comes from the formatter. */
export function trendLine(percent: string): string {
  return `30-day trend ${percent}`;
}

/** Polite live-region announcement once the value settles (a11y, foil-reveal.md §65). */
export function valueAnnounce(formattedValue: string, trendFragment: string | null): string {
  const head = `Market value, ${formattedValue}`;
  return trendFragment ? `${head}, ${trendFragment}` : head;
}
