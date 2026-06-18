// Derived portfolio figures — the numbers the Vault screen shows beneath the total.
// Pure functions so the change/percent math is unit-tested without a render.

import type { CollectionItem, Portfolio } from "./models";

export type PortfolioChange = {
  /** Signed € change of the latest valuation vs the previous snapshot. */
  absolute: number;
  /** Signed fraction, e.g. 0.042 for +4.2%. Null when there's no prior to compare. */
  fraction: number | null;
  direction: "up" | "down" | "flat";
};

/** Compare the latest snapshot to the previous one. No previous → no change to show. */
export function portfolioChange(p: Portfolio): PortfolioChange | null {
  if (!p.previous) return null;
  const absolute = round2(p.latest.totalValueEur - p.previous.totalValueEur);
  const base = p.previous.totalValueEur;
  const fraction = base > 0 ? (p.latest.totalValueEur - base) / base : null;
  return { absolute, fraction, direction: directionOf(absolute) };
}

/** A holding's contribution to the total: current unit price × quantity. */
export function itemValue(item: CollectionItem): number | null {
  const unit = item.price?.value;
  if (unit == null) return null;
  return round2(unit * item.quantity);
}

/** Sum the priced holdings; unpriced (long-tail) items contribute 0, surfaced separately. */
export function collectionTotal(items: CollectionItem[]): number {
  return round2(
    items.reduce((sum, item) => sum + (itemValue(item) ?? 0), 0)
  );
}

function directionOf(n: number): PortfolioChange["direction"] {
  if (n > 0) return "up";
  if (n < 0) return "down";
  return "flat";
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
