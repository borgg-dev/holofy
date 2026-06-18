import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { createFixtureClient } from "../client";
import { countUpValue } from "../countUp";
import { resetFixtures } from "../fixtures";
import {
  MappingError,
  mapPortfolio,
  mapScanResponse,
  parseMoney,
} from "../mapping";
import { collectionTotal, itemValue, portfolioChange } from "../portfolio";
import type { WirePortfolio, WireScanResponse } from "../types";
import type { CollectionItem, Portfolio } from "../models";

afterEach(() => resetFixtures());

describe("parseMoney", () => {
  it("parses a Decimal-as-string into euros", () => {
    assert.equal(parseMoney("757.10"), 757.1);
  });
  it("preserves null for a long-tail card", () => {
    assert.equal(parseMoney(null), null);
  });
  it("returns null for a non-numeric string rather than NaN", () => {
    assert.equal(parseMoney("not-a-price"), null);
  });
});

describe("mapScanResponse — resolved", () => {
  const resolved: WireScanResponse = {
    outcome: "resolved",
    card: {
      identity: {
        canonical_id: "origins-8",
        game: { id: "pokemon", name: "Pokémon" },
        name: "Tidecaller Leviath",
        set_name: "Origins Vault",
        collector_number: "8/120",
        language: "en",
        variant: "holo",
      },
      confidence: 0.97,
      price: {
        canonical_id: "origins-8",
        currency: "EUR",
        value: "289.00",
        basis: "trend",
        low: "120.00",
        avg30: "271.40",
        source: "cardmarket",
        as_of: "2026-06-18T00:00:00Z",
        age_hours: 6,
        listing_url: null,
      },
    },
    choices: null,
    price_delta: null,
  };

  it("maps to a resolved result with parsed money and a Date", () => {
    const r = mapScanResponse(resolved);
    assert.equal(r.outcome, "resolved");
    if (r.outcome !== "resolved") return;
    assert.equal(r.identity.canonicalId, "origins-8");
    assert.equal(r.identity.collectorNumber, "8/120");
    assert.equal(r.price?.value, 289);
    assert.equal(r.price?.avg30, 271.4);
    assert.ok(r.price?.asOf instanceof Date);
  });

  it("throws if a resolved payload has no card", () => {
    assert.throws(() => mapScanResponse({ ...resolved, card: null }), MappingError);
  });
});

describe("mapScanResponse — needs_confirmation", () => {
  const confirm: WireScanResponse = {
    outcome: "needs_confirmation",
    card: null,
    choices: [
      {
        identity: {
          canonical_id: "origins-12",
          game: { id: "pokemon", name: "Pokémon" },
          name: "Emberwyrm Sovereign",
          set_name: "Origins Vault",
          collector_number: "12/120",
          language: "en",
          variant: "holo",
        },
        confidence: 0.61,
        price: {
          canonical_id: "origins-12",
          currency: "EUR",
          value: "757.10",
          basis: "trend",
          low: "100.00",
          avg30: "529.99",
          source: "cardmarket",
          as_of: "2026-06-18T00:00:00Z",
          age_hours: 6,
          listing_url: null,
        },
      },
      {
        identity: {
          canonical_id: "echo-12",
          game: { id: "pokemon", name: "Pokémon" },
          name: "Emberwyrm Sovereign",
          set_name: "Echo Reprint",
          collector_number: "12/95",
          language: "en",
          variant: "holo",
        },
        confidence: 0.55,
        price: {
          canonical_id: "echo-12",
          currency: "EUR",
          value: "24.50",
          basis: "trend",
          low: "9.00",
          avg30: "22.10",
          source: "cardmarket",
          as_of: "2026-06-18T00:00:00Z",
          age_hours: 6,
          listing_url: null,
        },
      },
    ],
    price_delta: "732.60",
  };

  it("maps the top-2 and the € delta the user disambiguates on", () => {
    const r = mapScanResponse(confirm);
    assert.equal(r.outcome, "needs_confirmation");
    if (r.outcome !== "needs_confirmation") return;
    assert.equal(r.choices.length, 2);
    assert.equal(r.priceDelta, 732.6);
    // The delta equals the gap between the two priced choices.
    const gap = Math.abs(
      (r.choices[0]!.price!.value ?? 0) - (r.choices[1]!.price!.value ?? 0)
    );
    assert.equal(Math.round(gap * 100) / 100, r.priceDelta);
  });

  it("throws when fewer than two choices are offered", () => {
    assert.throws(
      () => mapScanResponse({ ...confirm, choices: [confirm.choices![0]!] }),
      MappingError
    );
  });
});

describe("portfolio derivation", () => {
  const wire: WirePortfolio = {
    latest: {
      total_value_eur: "350.00",
      total_cost_basis_eur: null,
      item_count: 3,
      valuation_basis: "trend",
      captured_at: "2026-06-18T00:00:00Z",
    },
    previous: {
      total_value_eur: "300.00",
      total_cost_basis_eur: null,
      item_count: 3,
      valuation_basis: "trend",
      captured_at: "2026-06-11T00:00:00Z",
    },
  };

  it("computes a signed change and direction vs the previous snapshot", () => {
    const p: Portfolio = mapPortfolio(wire);
    const change = portfolioChange(p);
    assert.ok(change);
    assert.equal(change!.absolute, 50);
    assert.equal(change!.direction, "up");
    assert.ok(Math.abs(change!.fraction! - 0.1667) < 0.001);
  });

  it("returns no change when there's no previous snapshot", () => {
    const p = mapPortfolio({ ...wire, previous: null });
    assert.equal(portfolioChange(p), null);
  });
});

describe("collection valuation", () => {
  const priced = (value: number | null, qty: number): CollectionItem => ({
    id: "x",
    identity: {
      canonicalId: "c",
      game: { id: "pokemon", name: "Pokémon" },
      name: "n",
      setName: "s",
      collectorNumber: "1/1",
      language: "en",
      variant: "holo",
    },
    condition: "near_mint",
    quantity: qty,
    acquiredPriceEur: null,
    price:
      value == null
        ? null
        : {
            canonicalId: "c",
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
  });

  it("multiplies unit price by quantity", () => {
    assert.equal(itemValue(priced(61.4, 2)), 122.8);
  });

  it("treats an unpriced holding as no value, not zero-priced", () => {
    assert.equal(itemValue(priced(null, 1)), null);
  });

  it("sums priced holdings and skips unpriced ones", () => {
    assert.equal(collectionTotal([priced(100, 1), priced(null, 3), priced(50, 2)]), 200);
  });
});

describe("countUpValue", () => {
  it("is exactly 0 at the start and the target at the end", () => {
    assert.equal(countUpValue(757.1, 0, 1100), 0);
    assert.equal(countUpValue(757.1, 1100, 1100), 757.1);
    assert.equal(countUpValue(757.1, 2000, 1100), 757.1);
  });
  it("eases out — past the midpoint of value before the midpoint of time", () => {
    const mid = countUpValue(100, 550, 1100);
    assert.ok(mid > 50, `expected >50 at half time, got ${mid}`);
    assert.ok(mid < 100);
  });
  it("returns the target immediately for a zero duration (reduced motion)", () => {
    assert.equal(countUpValue(42.5, 0, 0), 42.5);
  });
});

describe("fixture client — the offline demo path", () => {
  it("resolves the high-confidence bundle straight to a reveal", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const r = await client.scan({ bundleId: "mock-high-confidence" });
    assert.equal(r.outcome, "resolved");
  });

  it("routes the default bundle to a confirm with the top-2 + delta", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const r = await client.scan({ bundleId: "anything-else" });
    assert.equal(r.outcome, "needs_confirmation");
    if (r.outcome !== "needs_confirmation") return;
    assert.equal(r.choices.length, 2);
    assert.equal(r.priceDelta, 732.6);
  });

  it("reflects an added card in the collection and portfolio total", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const before = await client.portfolio();
    await client.addToCollection({ canonicalId: "origins-12", condition: "near_mint" });
    const after = await client.portfolio();
    const list = await client.listCollection();
    assert.equal(after.latest.itemCount, before.latest.itemCount + 1);
    assert.ok(after.latest.totalValueEur > before.latest.totalValueEur);
    assert.ok(list.some((i) => i.identity.canonicalId === "origins-12"));
  });
});
