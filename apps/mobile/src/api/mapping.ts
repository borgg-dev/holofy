// Wire → model mapping. Pure, framework-free, and the unit of the API client's tests.
//
// The one subtlety worth stating: money crosses the wire as a *string* (the backend
// serializes Decimal that way to keep cents exact). Parsing it to a JS number here is a
// lossy step in theory, but card prices live well inside the 2^53 safe-integer range at
// cent precision, and the UI needs a number to format and to count up. We parse once, at
// the boundary, so no screen ever sees a raw string or re-parses.

import type {
  Authenticity,
  AuthenticitySignal,
  AxisProvenance,
  BatchScan,
  BatchScanItem,
  CardIdentity,
  CollectionItem,
  GradingAxis,
  Portfolio,
  PortfolioSnapshot,
  Pregrade,
  PriceQuote,
  RiskBand,
  ScanChoice,
  ScanResult,
  SubScore,
  TrainingConsent,
} from "./models";
import type {
  WireAuthenticityResponse,
  WireAuthenticitySignal,
  WireBatchScanItem,
  WireBatchScanResponse,
  WireCardIdentity,
  WireCollectionItem,
  WireConfirmationChoice,
  WireConsentState,
  WirePortfolio,
  WirePortfolioSnapshot,
  WirePregradeResponse,
  WirePriceQuote,
  WireRiskBand,
  WireScanResponse,
  WireScannedCard,
  WireSubScore,
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
    game: { id: w.game.id, name: w.game.name },
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

// ── Stack / batch scan ───────────────────────────────────────────────────────

function mapBatchItem(w: WireBatchScanItem): BatchScanItem {
  const base = { count: w.count, captureRefs: w.capture_refs };
  switch (w.outcome) {
    case "resolved": {
      if (!w.card) throw new MappingError("Batch item resolved without a card.");
      const c = mapChoice(w.card);
      return { outcome: "resolved", ...base, identity: c.identity, confidence: c.confidence, price: c.price };
    }
    case "needs_confirmation": {
      const choices = w.choices ?? [];
      if (choices.length < 2) throw new MappingError("Batch confirmation needs two choices.");
      return {
        outcome: "needs_confirmation",
        ...base,
        choices: choices.map(mapChoice),
        priceDelta: parseMoney(w.price_delta),
      };
    }
    case "unrecognized":
      return { outcome: "unrecognized", ...base };
    case "quota_exceeded":
      return { outcome: "quota_exceeded", ...base };
    default:
      // The server added an outcome the client doesn't model yet — fail loudly at the
      // boundary rather than silently dropping a card the user flipped.
      throw new MappingError(`Unknown batch outcome: ${(w as WireBatchScanItem).outcome}`);
  }
}

export function mapBatchScan(w: WireBatchScanResponse): BatchScan {
  return {
    items: w.items.map(mapBatchItem),
    quota: {
      limit: w.quota.limit,
      charged: w.quota.charged,
      remaining: w.quota.remaining,
      rejected: w.quota.rejected,
    },
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

// ── Pre-grade ────────────────────────────────────────────────────────────────

// Centering is the one axis we measure in-house (pixel-level); the rest are bought
// behind the GradingProvider seam (apps/api/app/grading), so their provenance is
// `estimated`. An axis read with low confidence is surfaced as `limited` — the UI
// widens its presentation rather than asserting false precision (gauge spec §53).
const MEASURED_AXES: ReadonlySet<GradingAxis> = new Set<GradingAxis>(["centering"]);

/** Below this measurement confidence, an axis is shown as `limited`, not asserted. */
export const LIMITED_CONFIDENCE = 0.55;

export function axisProvenance(axis: GradingAxis, confidence: number): AxisProvenance {
  if (confidence < LIMITED_CONFIDENCE) return "limited";
  return MEASURED_AXES.has(axis) ? "measured" : "estimated";
}

function mapSubScore(w: WireSubScore): SubScore {
  return {
    axis: w.axis,
    score: w.score,
    confidence: w.confidence,
    provenance: axisProvenance(w.axis, w.confidence),
  };
}

export function mapPregrade(w: WirePregradeResponse): Pregrade {
  if (w.status === "estimated") {
    if (!w.probability || !w.sub_scores || w.confidence == null) {
      throw new MappingError("Pre-grade estimated without a probability range, sub-scores, or confidence.");
    }
    const p = w.probability;
    return {
      status: "estimated",
      range: {
        likelyLow: p.likely_low,
        likelyHigh: p.likely_high,
        atLeast: p.at_least,
        pAtLeast: p.p_at_least,
      },
      subScores: w.sub_scores.map(mapSubScore),
      confidence: w.confidence,
      disclaimer: w.disclaimer,
    };
  }

  const reasons = w.reasons ?? [];
  if (reasons.length === 0) {
    throw new MappingError("Pre-grade retake carried no coaching reasons.");
  }
  return { status: "retake", reasons, disclaimer: w.disclaimer };
}

// ── Authenticity ─────────────────────────────────────────────────────────────

// The wire band is snake_case; the model is camelCase. This is the only place the two
// vocabularies meet, so the rest of the app never sees a snake-cased band.
const BAND_FROM_WIRE: Record<WireRiskBand, RiskBand> = {
  strong_signals: "strongSignals",
  inconclusive: "inconclusive",
  elevated_risk: "elevatedRisk",
};

function mapSignal(w: WireAuthenticitySignal): AuthenticitySignal {
  return {
    kind: w.kind,
    observation: w.observation,
    confidence: w.confidence,
    detail: w.detail,
  };
}

export function mapAuthenticity(w: WireAuthenticityResponse): Authenticity {
  if (w.status === "assessed") {
    if (!w.assessment) {
      throw new MappingError("Authenticity assessed without an assessment payload.");
    }
    const a = w.assessment;
    if (a.signals.length === 0) {
      throw new MappingError("Authenticity assessed without any signal reads.");
    }
    return {
      status: "assessed",
      band: BAND_FROM_WIRE[a.risk_band],
      confidence: a.confidence,
      signals: a.signals.map(mapSignal),
      recommendAuthentication: a.recommend_authentication,
      referenceValueEur: a.reference_value_eur,
      disclaimer: w.disclaimer,
    };
  }

  // Both refuse-paths carry reasons; the status keeps them apart so the UI shows the
  // right framing — "one more pass" for a poor capture vs "not needed at this value".
  const reasons = w.reasons ?? [];
  if (reasons.length === 0) {
    throw new MappingError(`Authenticity ${w.status} carried no reasons to explain it.`);
  }
  return {
    status: w.status === "retake" ? "retake" : "notAssessed",
    reasons,
    disclaimer: w.disclaimer,
  };
}

// ── Training consent ─────────────────────────────────────────────────────────

export function mapConsent(w: WireConsentState): TrainingConsent {
  return {
    granted: w.granted,
    consented: {
      scans: w.consented.scans,
      pregrades: w.consented.pregrades,
      authenticity: w.consented.authenticity,
    },
  };
}

/** Total captures currently feeding the training lake — the figure the copy speaks to. */
export function consentedTotal(consent: TrainingConsent): number {
  const { scans, pregrades, authenticity } = consent.consented;
  return scans + pregrades + authenticity;
}

/** Thrown when a wire payload is structurally valid JSON but violates the contract. */
export class MappingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MappingError";
  }
}
