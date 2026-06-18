// Derived portfolio figures — the numbers the Vault screen shows beneath the total.
// Pure functions so the change/percent math is unit-tested without a render.

import { gameDisplay, type CardGame, type CollectionItem, type GameDisplay, type Portfolio } from "./models";

/** One game's holdings, grouped for the Vault — the section the screen renders. */
export type GameGroup = {
  game: GameDisplay;
  /** This game's holdings, richest first. */
  items: CollectionItem[];
  /** Sum of the priced holdings in this game (euros). */
  subtotal: number;
  /** Total cards in this game, counting quantity. */
  cardCount: number;
};

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

/**
 * Group the Vault by game for the sectioned view. Games are ordered by subtotal
 * descending (the biggest collection leads); within a game, holdings are ordered by
 * contribution descending, with unpriced (no-comp) cards last. The grouping is stable
 * for ties — original collection order breaks them — so the list doesn't reshuffle on
 * an equal-value add.
 */
export function groupByGame(items: CollectionItem[]): GameGroup[] {
  const order: string[] = [];
  // The first card of a game settles the bucket's label — recognition is consistent
  // per id, so its name is stable across the group.
  const games = new Map<string, CardGame>();
  const byGame = new Map<string, CollectionItem[]>();
  for (const item of items) {
    const { game } = item.identity;
    let bucket = byGame.get(game.id);
    if (!bucket) {
      bucket = [];
      byGame.set(game.id, bucket);
      games.set(game.id, game);
      order.push(game.id);
    }
    bucket.push(item);
  }

  const groups = order.map((id) => {
    const bucket = byGame.get(id)!;
    const sorted = [...bucket].sort((a, b) => (itemValue(b) ?? 0) - (itemValue(a) ?? 0));
    return {
      game: gameDisplay(games.get(id)!),
      items: sorted,
      subtotal: collectionTotal(bucket),
      cardCount: bucket.reduce((n, it) => n + it.quantity, 0),
    };
  });

  return groups.sort((a, b) => b.subtotal - a.subtotal);
}

function directionOf(n: number): PortfolioChange["direction"] {
  if (n > 0) return "up";
  if (n < 0) return "down";
  return "flat";
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
