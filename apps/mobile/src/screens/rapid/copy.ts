// All rapid/stack microcopy in one place — product strings, not placeholders, and the
// seam localization (FR→ES→IT→DE→EN) swaps. The voice is the rest of the app's: plain,
// honest, the collector's own words. The free tier is 8 ID scans/day (master plan §4).

// ── Capture phase ──────────────────────────────────────────────────────────────

export const RAPID_EYEBROW = "RAPID STACK";
export const RAPID_TITLE = "Flip through the pile";
/** Sets the ID + value-only promise before the first flip — the boundary, stated up front. */
export const RAPID_SUBTITLE = "We'll read and price each card. Grading and authenticity stay one-at-a-time.";

export const CAPTURE_CTA_REST = "Capture card";
export const CAPTURE_CTA_DONE = "All flipped";
export const REVIEW_CTA = "Review stack";

/** Empty filmstrip — the first instruction, gone the moment a card lands. */
export const STRIP_EMPTY = "Captured cards land here as you flip.";

export const PENDING_LABEL = "Reading…";
export const UNREADABLE_LABEL = "Missed";

/** Running header — kept terse; the figures carry it. */
export function runningCount(cards: number): string {
  return `${cards} ${cards === 1 ? "card" : "cards"}`;
}

/** SR announce on a fresh card landing in the strip. */
export function addedAnnounce(name: string, formattedPrice: string | null): string {
  return formattedPrice ? `${name} added, ${formattedPrice}` : `${name} added`;
}

/** SR announce when a flip dedupes onto a card already in the strip. */
export function mergedAnnounce(name: string, times: number): string {
  return `${name} again — now ${times} in your stack`;
}

/** SR announce for a flip that read no card. */
export const MISS_ANNOUNCE = "No card read — flip it again to catch it";

/** SR announce of the live running total, spoken after each change settles. */
export function totalAnnounce(formattedTotal: string, cards: number): string {
  return `Stack total ${formattedTotal} across ${cards} ${cards === 1 ? "card" : "cards"}`;
}

// ── Review phase ─────────────────────────────────────────────────────────────

export const REVIEW_EYEBROW = "REVIEW YOUR STACK";
export const REVIEW_TITLE = "Add the keepers";
export const REVIEW_LOADING = "Reading the stack…";

export const SECTION_RESOLVED = "Ready to add";
export const SECTION_CONFIRM = "Confirm the variant";
export const SECTION_UNRECOGNIZED = "Couldn't read";
export const SECTION_QUOTA = "Past today's free scans";

/** Sub-line under the resolved section — the bulk action's framing. */
export const RESOLVED_HINT = "Select the cards to keep, then add them all to your Vault in one go.";

/** Each needs_confirmation card carries its own delta line. */
export function confirmHint(formattedDelta: string | null): string {
  return formattedDelta
    ? `These two differ by ${formattedDelta} — pick the one in your hand.`
    : "Two close matches — pick the one in your hand.";
}

export const UNRECOGNIZED_HINT = "These flips didn't read. Re-capture them one at a time for a cleaner shot.";
export const RECAPTURE_CTA = "Re-capture";

/** Caption for the unrecognized section — count-aware so it never reads "1 flips". */
export function unreadCaption(flips: number): string {
  return `${flips} ${flips === 1 ? "flip" : "flips"} didn't read.`;
}

/** The quota block is shown calmly — a free-tier limit reached, never an error. */
export function quotaHint(rejected: number, limit: number): string {
  return `${rejected} ${rejected === 1 ? "card" : "cards"} went past your ${limit} free scans for today. Your daily count resets tomorrow, or go unlimited with Collector+.`;
}
export const QUOTA_UPGRADE_CTA = "See Collector+";

/** Bulk-add button, with the selected count when any are picked. */
export function bulkAddLabel(selected: number): string {
  if (selected === 0) return "Add to Vault";
  return `Add ${selected} to Vault`;
}
export const BULK_ADD_HINT = "Adds every selected card to your Vault at once.";
export const SELECT_ALL = "Select all";
export const SELECT_NONE = "Clear";

/** The ID + value-only boundary, made explicit on every resolved row. */
export const GRADE_AFFORDANCE = "Grade / Check authenticity";
export const GRADE_AFFORDANCE_HINT =
  "Opens the single guided capture — grading and authenticity need their own careful shots.";

export const REVIEW_BACK = "‹ Back to flipping";
export const ADDED_TOAST = "Added to your Vault";

/** Review is empty of keepers — nothing resolved (all misses / over quota). */
export const NOTHING_TO_ADD_TITLE = "Nothing read cleanly this pass";
export const NOTHING_TO_ADD_SUB = "Re-capture the missed flips, or scan them one at a time.";
