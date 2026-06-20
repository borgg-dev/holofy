import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  conditionLabel,
  formatTrendPercent,
  identityA11yLabel,
  identitySubline,
  trendA11y,
  trendFromQuote,
  variantLabel,
} from "../format";
import type { CardIdentity, PriceQuote } from "../../../api/models";

const EMBERWYRM: CardIdentity = {
  canonicalId: "origins-12",
  game: { id: "pokemon", name: "Pokémon" },
  name: "Emberwyrm Sovereign",
  setName: "Origins Vault",
  collectorNumber: "12/120",
  language: "en",
  variant: "holo",
  imageUrl: null,
};

function quote(value: number | null, avg30: number | null): PriceQuote {
  return {
    canonicalId: "origins-12",
    currency: "EUR",
    value,
    basis: "trend",
    low: null,
    avg30,
    source: "cardmarket",
    asOf: new Date(),
    ageHours: 1,
    listingUrl: null,
  };
}

describe("identitySubline", () => {
  it("joins set, number, uppercased language, and variant with middots", () => {
    assert.equal(identitySubline(EMBERWYRM), "Origins Vault · 12/120 · EN · Holo");
  });
});

describe("identityA11yLabel", () => {
  it("spells out the card for a screen reader", () => {
    assert.equal(
      identityA11yLabel(EMBERWYRM),
      "Emberwyrm Sovereign, Origins Vault, number 12 of 120, English, holo"
    );
  });
});

describe("variant / condition labels", () => {
  it("title-cases variants and conditions", () => {
    assert.equal(variantLabel("reverse_holo"), "Reverse holo");
    assert.equal(variantLabel("first_edition"), "1st Edition");
    assert.equal(conditionLabel("near_mint"), "Near mint");
  });
});

describe("trendFromQuote", () => {
  it("derives a positive fraction when value is above the 30-day average", () => {
    const t = trendFromQuote(quote(529.99 * 1.042, 529.99));
    assert.ok(t);
    assert.equal(t!.direction, "up");
    assert.equal(Math.round(t!.fraction * 1000) / 1000, 0.042);
  });

  it("reads a dip as down, not an error", () => {
    const t = trendFromQuote(quote(90, 100));
    assert.equal(t!.direction, "down");
  });

  it("returns null with no comparable average", () => {
    assert.equal(trendFromQuote(quote(10, null)), null);
    assert.equal(trendFromQuote(null), null);
  });
});

describe("formatTrendPercent", () => {
  it("shows a sign and a real minus glyph, one decimal", () => {
    assert.equal(formatTrendPercent(0.042), "+4,2%");
    assert.equal(formatTrendPercent(-0.018), "−1,8%");
  });
});

describe("trendA11y", () => {
  it("pairs the word with the number, never color-only", () => {
    assert.equal(trendA11y({ fraction: 0.042, direction: "up" }), "up 4,2 percent over 30 days");
  });
});
