// App-facing models — what screens and view-logic consume.
//
// The boundary with the wire layer is deliberate: money is a `number` in major units
// (euros, the unit ValueText formats), timestamps are `Date`, and the two scan outcomes
// are a discriminated union so a screen `switch`es on `outcome` and the compiler proves
// the right fields are present. Nothing here knows about HTTP.

import type { WireCondition, WireVariant } from "./types";

export type Variant = WireVariant;
export type Condition = WireCondition;

export type CardIdentity = {
  canonicalId: string;
  name: string;
  setName: string;
  /** Already in "12/120" form from recognition. */
  collectorNumber: string;
  /** ISO-639 code, e.g. "en", "de". */
  language: string;
  variant: Variant;
};

export type PriceQuote = {
  canonicalId: string;
  currency: string;
  /** Major units (euros), or null for a long-tail card with no liquid comp. */
  value: number | null;
  /** Which statistic `value` is — "trend" | "avg_30d" | … (PriceBasis). */
  basis: string;
  low: number | null;
  avg30: number | null;
  /** Provenance — "cardmarket" | "tcgdex" | "mock" … shown so value isn't a black box. */
  source: string;
  asOf: Date;
  ageHours: number;
  listingUrl: string | null;
};

/** A confidently identified, priced card — the reveal screen's happy path. */
export type ResolvedScan = {
  outcome: "resolved";
  identity: CardIdentity;
  confidence: number;
  price: PriceQuote | null;
};

/** One option the user picks between when recognition isn't sure. */
export type ScanChoice = {
  identity: CardIdentity;
  confidence: number;
  price: PriceQuote | null;
};

/** Low-confidence top-2 + the € delta that justifies asking — never a silent guess. */
export type NeedsConfirmationScan = {
  outcome: "needs_confirmation";
  choices: ScanChoice[];
  /** Absolute € gap between the two choices, when both are priced. */
  priceDelta: number | null;
};

export type ScanResult = ResolvedScan | NeedsConfirmationScan;

export type CollectionItem = {
  id: string;
  identity: CardIdentity;
  condition: Condition;
  quantity: number;
  /** What the collector paid, in euros, if recorded. */
  acquiredPriceEur: number | null;
  price: PriceQuote | null;
};

export type PortfolioSnapshot = {
  totalValueEur: number;
  totalCostBasisEur: number | null;
  itemCount: number;
  valuationBasis: string;
  capturedAt: Date;
};

export type Portfolio = {
  latest: PortfolioSnapshot;
  previous: PortfolioSnapshot | null;
};
