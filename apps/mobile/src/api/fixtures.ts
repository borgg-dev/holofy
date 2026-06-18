// Fixture backend — lets every screen render, and the whole scan→reveal→collect flow
// run, with no live server. The data mirrors apps/api's mock providers (the two Emberwyrm
// Sovereign printings ~31× apart in price is the canonical variant-confusion case the
// confirm step exists for), so what's seen here matches what the real mock API returns.
// The cards are Holofy's own invention — original creatures and sets, no third-party IP.
//
// This is the *wire* shape (strings for money, snake_case): it flows through the same
// mapping layer as a real response, so the fixture path exercises the real code, not a
// parallel one.

import type {
  WireCardIdentity,
  WireCollectionItem,
  WirePortfolio,
  WirePriceQuote,
  WireScanResponse,
} from "./types";

const AS_OF = "2026-06-18T00:00:00Z";

function identity(
  canonicalId: string,
  name: string,
  setName: string,
  collectorNumber: string,
  variant: WireCardIdentity["variant"]
): WireCardIdentity {
  return {
    canonical_id: canonicalId,
    name,
    set_name: setName,
    collector_number: collectorNumber,
    language: "en",
    variant,
  };
}

function price(
  canonicalId: string,
  value: string,
  avg30: string,
  low: string
): WirePriceQuote {
  return {
    canonical_id: canonicalId,
    currency: "EUR",
    value,
    basis: "trend",
    low,
    avg30,
    source: "cardmarket",
    as_of: AS_OF,
    age_hours: 6,
    listing_url: null,
  };
}

const EMBERWYRM_ORIGINS = identity("origins-12", "Emberwyrm Sovereign", "Origins Vault", "12/120", "holo");
const EMBERWYRM_ECHO = identity("echo-12", "Emberwyrm Sovereign", "Echo Reprint", "12/95", "holo");
const TIDECALLER_ORIGINS = identity("origins-8", "Tidecaller Leviath", "Origins Vault", "8/120", "holo");
const GROVEKEEPER_WILDGROWTH = identity("wild-15", "Grovekeeper Thornmaw", "Wildgrowth", "15/88", "holo");

const PRICES: Record<string, WirePriceQuote> = {
  "origins-12": price("origins-12", "757.10", "529.99", "100.00"),
  "echo-12": price("echo-12", "24.50", "22.10", "9.00"),
  "origins-8": price("origins-8", "289.00", "271.40", "120.00"),
  "wild-15": price("wild-15", "61.40", "58.90", "28.00"),
};

/** High-confidence single → reveal commits straight through (bundle "mock-high-confidence"). */
export const RESOLVED_SCAN: WireScanResponse = {
  outcome: "resolved",
  card: { identity: TIDECALLER_ORIGINS, confidence: 0.97, price: PRICES["origins-8"] },
  choices: null,
  price_delta: null,
};

/** Low-confidence top-2 with a ~€733 delta → the confirm screen (default mock bundle). */
export const NEEDS_CONFIRMATION_SCAN: WireScanResponse = {
  outcome: "needs_confirmation",
  card: null,
  choices: [
    { identity: EMBERWYRM_ORIGINS, confidence: 0.61, price: PRICES["origins-12"] },
    { identity: EMBERWYRM_ECHO, confidence: 0.55, price: PRICES["echo-12"] },
  ],
  price_delta: "732.60",
};

/** Map a capture bundle id to a fixture, matching apps/api's recognition mock keys. */
export function scanFixtureFor(bundleId: string): WireScanResponse {
  if (bundleId === "mock-high-confidence") return RESOLVED_SCAN;
  return NEEDS_CONFIRMATION_SCAN;
}

// A starter Vault — two confidently-owned holdings, so the portfolio reads as a real
// (if small) collection rather than an empty shell. The flow adds to this in memory.
let collection: WireCollectionItem[] = [
  {
    id: "fixture-tidecaller",
    identity: TIDECALLER_ORIGINS,
    condition: "near_mint",
    quantity: 1,
    acquired_price_eur: "210.00",
    price: PRICES["origins-8"]!,
  },
  {
    id: "fixture-grovekeeper",
    identity: GROVEKEEPER_WILDGROWTH,
    condition: "excellent",
    quantity: 2,
    acquired_price_eur: "44.00",
    price: PRICES["wild-15"]!,
  },
];

export function fixtureCollection(): WireCollectionItem[] {
  return collection.map((item) => ({ ...item }));
}

export function fixtureAddToCollection(
  canonicalId: string,
  condition: WireCollectionItem["condition"],
  quantity = 1
): WireCollectionItem {
  const known =
    [EMBERWYRM_ORIGINS, EMBERWYRM_ECHO, TIDECALLER_ORIGINS, GROVEKEEPER_WILDGROWTH].find(
      (c) => c.canonical_id === canonicalId
    ) ?? EMBERWYRM_ORIGINS;
  const item: WireCollectionItem = {
    id: `fixture-${canonicalId}-${collection.length}`,
    identity: known,
    condition,
    quantity,
    acquired_price_eur: null,
    price: PRICES[canonicalId] ?? null,
  };
  collection = [...collection, item];
  return { ...item };
}

function sumCollection(items: WireCollectionItem[]): { total: number; count: number } {
  let total = 0;
  let count = 0;
  for (const item of items) {
    count += item.quantity;
    const v = item.price?.value;
    if (v != null) total += Number(v) * item.quantity;
  }
  return { total: Math.round(total * 100) / 100, count };
}

/** The latest valuation, with a synthetic "yesterday" so the change delta has a base. */
export function fixturePortfolio(): WirePortfolio {
  const { total, count } = sumCollection(collection);
  const previousTotal = Math.round(total * 0.962 * 100) / 100; // +3.95% since the prior snapshot
  return {
    latest: {
      total_value_eur: total.toFixed(2),
      total_cost_basis_eur: null,
      item_count: count,
      valuation_basis: "trend",
      captured_at: AS_OF,
    },
    previous: {
      total_value_eur: previousTotal.toFixed(2),
      total_cost_basis_eur: null,
      item_count: count,
      valuation_basis: "trend",
      captured_at: "2026-06-11T00:00:00Z",
    },
  };
}

/** Reset mutable fixture state between tests/sessions. */
export function resetFixtures(): void {
  collection = [
    {
      id: "fixture-tidecaller",
      identity: TIDECALLER_ORIGINS,
      condition: "near_mint",
      quantity: 1,
      acquired_price_eur: "210.00",
      price: PRICES["origins-8"]!,
    },
    {
      id: "fixture-grovekeeper",
      identity: GROVEKEEPER_WILDGROWTH,
      condition: "excellent",
      quantity: 2,
      acquired_price_eur: "44.00",
      price: PRICES["wild-15"]!,
    },
  ];
}
