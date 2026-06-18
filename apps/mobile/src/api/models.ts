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

// ── Pre-grade ────────────────────────────────────────────────────────────────
//
// The honest grading contract, app-side. The headline is a *band* (likelyLow–
// likelyHigh), never a number; `pAtLeast` is the decision figure ("70% chance
// it's a 9 or better"). A capture too poor to grade is a `retake` outcome, not a
// confident wrong answer — kept as a discriminated union so a screen switches on
// `status` and the compiler proves the right fields are present.

export type GradingAxis = "centering" | "corners" | "edges" | "surface";

/**
 * How an axis was assessed. Centering is built in-house (pixel-level), so it's
 * `measured`; corners/edges/surface are bought, so `estimated`; `limited` flags an
 * axis the capture couldn't read well (e.g. surface under incomplete raking light).
 */
export type AxisProvenance = "measured" | "estimated" | "limited";

export type SubScore = {
  axis: GradingAxis;
  /** 1–10 estimate for this axis. */
  score: number;
  /** 0–1 — how trustworthy *this measurement* is, independent of how good the score is. */
  confidence: number;
  provenance: AxisProvenance;
};

/** The honest headline: a likely grade band, never a single number. */
export type GradeProbabilityRange = {
  likelyLow: number;
  likelyHigh: number;
  /** The floor the `pAtLeast` probability is measured against. */
  atLeast: number;
  /** P(true grade ≥ atLeast) — the figure a collector actually decides on. */
  pAtLeast: number;
};

/** Capture good enough to estimate: the band, four sub-scores, overall confidence. */
export type PregradeEstimate = {
  status: "estimated";
  range: GradeProbabilityRange;
  subScores: SubScore[];
  /** 0–1 overall confidence across the four axes. */
  confidence: number;
  disclaimer: string;
};

/** Capture too poor to grade honestly: coaching reasons to re-capture, never a grade. */
export type PregradeRetake = {
  status: "retake";
  reasons: string[];
  disclaimer: string;
};

export type Pregrade = PregradeEstimate | PregradeRetake;

// ── Training consent ─────────────────────────────────────────────────────────
//
// The user's explicit, revocable permission to let their captures improve Holofy's
// models — the data-loop moat. Deliberately separate from app-usage consent and OFF
// by default; the privacy screen reads and writes this. `granted` is the account-level
// switch; `consented` breaks it down so the copy can be specific and honest about what
// is actually being shared.

export type ConsentCounts = {
  scans: number;
  pregrades: number;
  authenticity: number;
};

export type TrainingConsent = {
  granted: boolean;
  consented: ConsentCounts;
};
