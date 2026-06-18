// Wire → model mapping. Pure, framework-free, and the unit of the API client's tests.
//
// The one subtlety worth stating: money crosses the wire as a *string* (the backend
// serializes Decimal that way to keep cents exact). Parsing it to a JS number here is a
// lossy step in theory, but card prices live well inside the 2^53 safe-integer range at
// cent precision, and the UI needs a number to format and to count up. We parse once, at
// the boundary, so no screen ever sees a raw string or re-parses.

import type {
  CardIdentity,
  CollectionItem,
  Portfolio,
  PortfolioSnapshot,
  PriceQuote,
  ScanChoice,
  ScanResult,
} from "./models";
import type {
  WireCardIdentity,
  WireCollectionItem,
  WireConfirmationChoice,
  WirePortfolio,
  WirePortfolioSnapshot,
  WirePriceQuote,
  WireScanResponse,
  WireScannedCard,
} from "./types";

/** Parse a Decimal-as-string money field to euros, preserving null. */
export function parseMoney(raw: string | null): number | null {
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function mapIdentity(w: WireCardIdentity): CardIdentity {
  return {
    canonicalId: w.canonical_id,
    name: w.name,
    setName: w.set_name,
    collectorNumber: w.collector_number,
    language: w.language,
    variant: w.variant,
  };
}

export function mapPrice(w: WirePriceQuote | null): PriceQuote | null {
  if (w == null) return null;
  return {
    canonicalId: w.canonical_id,
    currency: w.currency,
    value: parseMoney(w.value),
    basis: w.basis,
    low: parseMoney(w.low),
    avg30: parseMoney(w.avg30),
    source: w.source,
    asOf: new Date(w.as_of),
    ageHours: w.age_hours,
    listingUrl: w.listing_url,
  };
}

function mapChoice(w: WireConfirmationChoice | WireScannedCard): ScanChoice {
  return {
    identity: mapIdentity(w.identity),
    confidence: w.confidence,
    price: mapPrice(w.price),
  };
}

export function mapScanResponse(w: WireScanResponse): ScanResult {
  if (w.outcome === "resolved") {
    if (!w.card) {
      throw new MappingError("Scan resolved without a card.");
    }
    const c = mapChoice(w.card);
    return {
      outcome: "resolved",
      identity: c.identity,
      confidence: c.confidence,
      price: c.price,
    };
  }

  const choices = w.choices ?? [];
  if (choices.length < 2) {
    throw new MappingError("Confirmation needs two choices.");
  }
  return {
    outcome: "needs_confirmation",
    choices: choices.map(mapChoice),
    priceDelta: parseMoney(w.price_delta),
  };
}

export function mapCollectionItem(w: WireCollectionItem): CollectionItem {
  return {
    id: w.id,
    identity: mapIdentity(w.identity),
    condition: w.condition,
    quantity: w.quantity,
    acquiredPriceEur: parseMoney(w.acquired_price_eur),
    price: mapPrice(w.price),
  };
}

function mapSnapshot(w: WirePortfolioSnapshot): PortfolioSnapshot {
  return {
    totalValueEur: Number(w.total_value_eur),
    totalCostBasisEur: parseMoney(w.total_cost_basis_eur),
    itemCount: w.item_count,
    valuationBasis: w.valuation_basis,
    capturedAt: new Date(w.captured_at),
  };
}

export function mapPortfolio(w: WirePortfolio): Portfolio {
  return {
    latest: mapSnapshot(w.latest),
    previous: w.previous ? mapSnapshot(w.previous) : null,
  };
}

/** Thrown when a wire payload is structurally valid JSON but violates the contract. */
export class MappingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MappingError";
  }
}
