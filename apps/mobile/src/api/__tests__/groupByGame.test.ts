import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { groupByGame } from "../portfolio";
import { GAMES } from "../models";
import type { CollectionItem, GameId } from "../models";

let seq = 0;
function holding(game: GameId, value: number | null, quantity = 1): CollectionItem {
  const id = `h-${seq++}`;
  return {
    id,
    identity: {
      canonicalId: id,
      game,
      name: id,
      setName: "Inkwell Tides",
      collectorNumber: "1/1",
      language: "en",
      variant: "holo",
    },
    condition: "near_mint",
    quantity,
    acquiredPriceEur: null,
    price:
      value == null
        ? null
        : {
            canonicalId: id,
            currency: "EUR",
            value,
            basis: "trend",
            low: null,
            avg30: null,
            source: "mock",
            asOf: new Date(),
            ageHours: 0,
            listingUrl: null,
          },
  };
}

describe("groupByGame", () => {
  it("buckets holdings into one section per game", () => {
    const groups = groupByGame([
      holding("pokemon", 100),
      holding("lorcana", 50),
      holding("pokemon", 20),
    ]);
    assert.equal(groups.length, 2);
    assert.deepEqual(
      groups.map((g) => g.game.id).sort(),
      ["lorcana", "pokemon"]
    );
  });

  it("sums each game's priced holdings into its subtotal, counting quantity", () => {
    const groups = groupByGame([
      holding("pokemon", 100, 2), // 200
      holding("pokemon", 50, 1), // 50
    ]);
    assert.equal(groups.length, 1);
    assert.equal(groups[0]!.subtotal, 250);
    assert.equal(groups[0]!.cardCount, 3);
  });

  it("orders games by subtotal descending — the biggest collection leads", () => {
    const groups = groupByGame([
      holding("lorcana", 300),
      holding("pokemon", 80),
    ]);
    assert.deepEqual(
      groups.map((g) => g.game.id),
      ["lorcana", "pokemon"]
    );
  });

  it("orders holdings within a game by contribution descending, unpriced last", () => {
    const groups = groupByGame([
      holding("pokemon", 10),
      holding("pokemon", null),
      holding("pokemon", 90),
    ]);
    const values = groups[0]!.items.map((it) => it.price?.value ?? null);
    assert.deepEqual(values, [90, 10, null]);
  });

  it("excludes unpriced holdings from a subtotal but counts them in cardCount", () => {
    const groups = groupByGame([
      holding("lorcana", 40, 1),
      holding("lorcana", null, 2),
    ]);
    assert.equal(groups[0]!.subtotal, 40);
    assert.equal(groups[0]!.cardCount, 3);
  });

  it("attaches the registry game (nominative label + accent), not a raw id", () => {
    const [group] = groupByGame([holding("lorcana", 1)]);
    assert.equal(group!.game.name, GAMES.lorcana.name);
    assert.equal(group!.game.accent, GAMES.lorcana.accent);
  });

  it("returns no sections for an empty vault", () => {
    assert.deepEqual(groupByGame([]), []);
  });
});
