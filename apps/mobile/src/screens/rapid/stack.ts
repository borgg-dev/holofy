// The on-device live-stack model — the pure logic behind the rapid filmstrip and its
// running count + € total. Kept framework-free so it's unit-testable and never
// re-implemented in the screen.
//
// Two things happen as the user flips: a capture is appended, and — the honest part —
// a capture whose identity matches one already in the strip *merges* onto it (the count
// badge ticks up) instead of adding a duplicate row. This mirrors the backend's identity
// dedupe (apps/api batch_scan): flipping past the same card twice banks it once, so the
// live UX tells the same truth the server will. The authoritative result still comes from
// POST /scan/batch at confirm-time; this is the fast, tactile preview while flipping.

import type { BatchScanItem, CardIdentity, PriceQuote } from "@/api";

/** What one flip's quick on-device recognition produced — before the batch confirms it. */
export type CaptureRead =
  | { kind: "identified"; identity: CardIdentity; price: PriceQuote | null }
  // Recognized as a card but not confidently enough to name it here — the batch will
  // resolve or ask to confirm it. Held as its own pending row, never merged or priced.
  | { kind: "pending" }
  // No card read at all (a glare/blur flip) — surfaced so it reads as "missed", not lost.
  | { kind: "unreadable" };

/** One row in the live filmstrip: a flipped (or merged) capture with its current read. */
export type StripEntry = {
  /** Stable key for the row — the first capture that created it. */
  id: string;
  /** Every capture bundle that landed on this row, in flip order (≥1). */
  captureRefs: string[];
  read: CaptureRead;
};

export type StripTotals = {
  /** Distinct rows that resolved to a named card — what the running count shows. */
  cardCount: number;
  /** Total flips captured, including merges and misses — the honest "shots taken". */
  captureCount: number;
  /** Running € total across priced, identified rows (unit price × times flipped). */
  totalEur: number;
  /** Identified rows we couldn't price (no liquid comp) — surfaced so the total reads honest. */
  unpricedCount: number;
};

/** How a freshly captured flip changed the strip — drives the row animation + SR announce. */
export type AppliedCapture = {
  strip: StripEntry[];
  /** "added" = a new row; "merged" = it deduped onto an existing card (count ticked up). */
  effect: "added" | "merged";
  /** The row that was added or merged into — the one to animate / announce. */
  entry: StripEntry;
};

/** Two reads are the same card iff both are identified to the same canonical id. */
function sameCard(a: CaptureRead, b: CaptureRead): boolean {
  return (
    a.kind === "identified" &&
    b.kind === "identified" &&
    a.identity.canonicalId === b.identity.canonicalId
  );
}

/**
 * Apply one capture to the strip. An identified flip whose card is already present merges
 * onto that row (dedupe); anything else — a new card, a pending, or an unreadable — appends
 * its own row. Pure: returns a fresh strip and what changed, never mutates the input.
 */
export function applyCapture(
  strip: StripEntry[],
  captureRef: string,
  read: CaptureRead
): AppliedCapture {
  if (read.kind === "identified") {
    const idx = strip.findIndex((e) => sameCard(e.read, read));
    if (idx !== -1) {
      const target = strip[idx]!;
      const merged: StripEntry = { ...target, captureRefs: [...target.captureRefs, captureRef] };
      const next = strip.slice();
      next[idx] = merged;
      return { strip: next, effect: "merged", entry: merged };
    }
  }
  const entry: StripEntry = { id: captureRef, captureRefs: [captureRef], read };
  return { strip: [...strip, entry], effect: "added", entry };
}

/** Times this card was flipped — the count badge on a merged row (≥1; only shown when >1). */
export function entryCount(entry: StripEntry): number {
  return entry.captureRefs.length;
}

/** Roll up the strip into the live header figures. Misses and pendings don't price. */
export function stripTotals(strip: StripEntry[]): StripTotals {
  let cardCount = 0;
  let totalEur = 0;
  let unpricedCount = 0;
  for (const entry of strip) {
    if (entry.read.kind !== "identified") continue;
    cardCount += 1;
    const value = entry.read.price?.value;
    if (value == null) unpricedCount += 1;
    else totalEur += value * entryCount(entry);
  }
  const captureCount = strip.reduce((n, e) => n + entryCount(e), 0);
  return {
    cardCount,
    captureCount,
    totalEur: Math.round(totalEur * 100) / 100,
    unpricedCount,
  };
}

/** Every capture ref flipped this session, in order — the payload sent to POST /scan/batch. */
export function allCaptureRefs(strip: StripEntry[]): string[] {
  return strip.flatMap((e) => e.captureRefs);
}

// ── Confirm-at-end review ──────────────────────────────────────────────────────
//
// The review groups the authoritative batch result into the four lists the screen renders
// differently, then tracks what the collector has selected so a single "Add to Vault" commits
// the lot. Pure: the screen holds the selection in state and asks these helpers what to do.

export type ReviewGroups = {
  resolved: Extract<BatchScanItem, { outcome: "resolved" }>[];
  needsConfirmation: Extract<BatchScanItem, { outcome: "needs_confirmation" }>[];
  unrecognized: Extract<BatchScanItem, { outcome: "unrecognized" }>[];
  quotaExceeded: Extract<BatchScanItem, { outcome: "quota_exceeded" }>[];
};

/** Split a batch result into the four review sections, preserving arrival order within each. */
export function groupReview(items: BatchScanItem[]): ReviewGroups {
  const groups: ReviewGroups = {
    resolved: [],
    needsConfirmation: [],
    unrecognized: [],
    quotaExceeded: [],
  };
  for (const item of items) {
    switch (item.outcome) {
      case "resolved":
        groups.resolved.push(item);
        break;
      case "needs_confirmation":
        groups.needsConfirmation.push(item);
        break;
      case "unrecognized":
        groups.unrecognized.push(item);
        break;
      case "quota_exceeded":
        groups.quotaExceeded.push(item);
        break;
    }
  }
  return groups;
}

/** One card queued for the Vault — a chosen identity plus the quantity (its flip count). */
export type VaultAddition = { canonicalId: string; quantity: number };

/**
 * The bulk-add payload: every *selected* resolved card, plus each confirmed variant the user
 * picked. Undecided confirmation cards are deliberately left out — a stack never silently banks
 * a high-value variant the collector didn't confirm. `confirmedChoice` maps a confirmation card
 * (by its first capture ref, the row's stable key) to the choice index the user picked, or null.
 */
export function selectedAdditions(
  groups: ReviewGroups,
  resolvedSelected: ReadonlySet<string>,
  confirmedChoice: ReadonlyMap<string, number | null>
): VaultAddition[] {
  const additions: VaultAddition[] = [];
  for (const item of groups.resolved) {
    if (resolvedSelected.has(reviewKey(item))) {
      additions.push({ canonicalId: item.identity.canonicalId, quantity: item.count });
    }
  }
  for (const item of groups.needsConfirmation) {
    const pick = confirmedChoice.get(reviewKey(item));
    if (pick == null) continue;
    const choice = item.choices[pick];
    if (choice) additions.push({ canonicalId: choice.identity.canonicalId, quantity: item.count });
  }
  return additions;
}

/** Stable per-card key for selection state — the first capture that produced the item. */
export function reviewKey(item: BatchScanItem): string {
  return item.captureRefs[0] ?? item.outcome;
}
