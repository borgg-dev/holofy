import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { groupByGame } from "../portfolio";
import { gameAccent, gameDisplay, gameInitial } from "../models";
import type { CardGame, CollectionItem } from "../models";

const POKEMON: CardGame = { id: "pokemon", name: "Pokémon" };
const LORCANA: CardGame = { id: "lorcana", name: "Lorcana" };
// A game with no curated styling — the auto-create case the Vault must handle.
const ONE_PIECE: CardGame = { id: "one_piece", name: "One Piece" };

let seq = 0;
function holding(game: CardGame, value: number | null, quantity = 1): CollectionItem {
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
      imageUrl: null,
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
      holding(POKEMON, 100),
      holding(LORCANA, 50),
      holding(POKEMON, 20),
    ]);
    assert.equal(groups.length, 2);
    assert.deepEqual(
      groups.map((g) => g.game.id).sort(),
      ["lorcana", "pokemon"]
    );
  });

  it("sums each game's priced holdings into its subtotal, counting quantity", () => {
    const groups = groupByGame([
      holding(POKEMON, 100, 2), // 200
      holding(POKEMON, 50, 1), // 50
    ]);
    assert.equal(groups.length, 1);
    assert.equal(groups[0]!.subtotal, 250);
    assert.equal(groups[0]!.cardCount, 3);
  });

  it("orders games by subtotal descending — the biggest collection leads", () => {
    const groups = groupByGame([
      holding(LORCANA, 300),
      holding(POKEMON, 80),
    ]);
    assert.deepEqual(
      groups.map((g) => g.game.id),
      ["lorcana", "pokemon"]
    );
  });

  it("orders holdings within a game by contribution descending, unpriced last", () => {
    const groups = groupByGame([
      holding(POKEMON, 10),
      holding(POKEMON, null),
      holding(POKEMON, 90),
    ]);
    const values = groups[0]!.items.map((it) => it.price?.value ?? null);
    assert.deepEqual(values, [90, 10, null]);
  });

  it("excludes unpriced holdings from a subtotal but counts them in cardCount", () => {
    const groups = groupByGame([
      holding(LORCANA, 40, 1),
      holding(LORCANA, null, 2),
    ]);
    assert.equal(groups[0]!.subtotal, 40);
    assert.equal(groups[0]!.cardCount, 3);
  });

  it("labels and styles each section from the holding's own game data, not a registry", () => {
    const [group] = groupByGame([holding(LORCANA, 1)]);
    assert.equal(group!.game.name, "Lorcana");
    assert.equal(group!.game.accent, gameAccent("lorcana"));
    assert.equal(group!.game.initial, "L");
  });

  it("auto-creates a polished section for an uncurated game — no code change needed", () => {
    const groups = groupByGame([
      holding(POKEMON, 50),
      holding(ONE_PIECE, 120),
    ]);
    const onePiece = groups.find((g) => g.game.id === "one_piece");
    assert.ok(onePiece, "One Piece should group into its own section");
    // A name, a stable accent, and a glyph — indistinguishable in shape from a curated game.
    assert.equal(onePiece!.game.name, "One Piece");
    assert.equal(onePiece!.game.initial, "O");
    assert.equal(onePiece!.game.accent, gameAccent("one_piece"));
    assert.equal(onePiece!.subtotal, 120);
  });

  it("returns no sections for an empty vault", () => {
    assert.deepEqual(groupByGame([]), []);
  });
});

describe("gameDisplay derivation", () => {
  it("derives a stable accent from the id — same id, same color, always", () => {
    assert.equal(gameAccent("one_piece"), gameAccent("one_piece"));
    assert.equal(gameDisplay({ id: "one_piece", name: "One Piece" }).accent, gameAccent("one_piece"));
  });

  it("spreads varied ids across the palette rather than collapsing onto one color", () => {
    const ids = ["pokemon", "lorcana", "one_piece", "magic", "yugioh", "weiss"];
    const accents = new Set(ids.map(gameAccent));
    assert.ok(accents.size >= 3, `expected varied accents, got ${accents.size}`);
  });

  it("honors the curated override for flagship games", () => {
    assert.equal(gameAccent("pokemon"), "vaultTeal");
    assert.equal(gameAccent("lorcana"), "foilMagenta");
  });

  it("never derives a curated game's reserved color for an auto-created game", () => {
    // The two flagships' tints are reserved, so a new game can't visually masquerade as one.
    const reserved = new Set([gameAccent("pokemon"), gameAccent("lorcana")]);
    for (const id of ["one_piece", "magic", "yugioh", "digimon", "metazoo", "weiss", "starwars"]) {
      assert.ok(!reserved.has(gameAccent(id)), `${id} collided with a reserved flagship color`);
    }
  });

  it("derives the glyph from the first letter of the name, uppercased", () => {
    assert.equal(gameInitial("One Piece"), "O");
    assert.equal(gameInitial("pokémon"), "P");
    assert.equal(gameInitial("  digimon"), "D");
  });

  it("falls back to a placeholder glyph for an empty name rather than throwing", () => {
    assert.equal(gameInitial(""), "?");
    assert.equal(gameInitial("   "), "?");
  });
});
