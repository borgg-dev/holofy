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
  WireAuthenticityResponse,
  WireBatchScanResponse,
  WireCardIdentity,
  WireCollectionItem,
  WireConsentState,
  WirePortfolio,
  WirePregradeResponse,
  WirePriceQuote,
  WireScanResponse,
} from "./types";

const PREGRADE_DISCLAIMER =
  "Pre-screen estimate, not an official grade. This is decision support to help you " +
  "decide whether a card is worth submitting — it is not a PSA, CGC or BGS grade.";

// Verbatim from apps/api/app/schemas/authenticity.py :: AUTHENTICITY_DISCLAIMER — the
// defamation-safe framing must read identically wherever it surfaces.
const AUTHENTICITY_DISCLAIMER =
  "Private authenticity screening, not a verdict. This is a risk signal to help you " +
  "decide whether to pay for professional authentication — it is not a determination " +
  "that a card is genuine or counterfeit, and it is not an assessment of any seller.";

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

const PRICES = {
  "origins-12": price("origins-12", "757.10", "529.99", "100.00"),
  "echo-12": price("echo-12", "24.50", "22.10", "9.00"),
  "origins-8": price("origins-8", "289.00", "271.40", "120.00"),
  "wild-15": price("wild-15", "61.40", "58.90", "28.00"),
} satisfies Record<string, WirePriceQuote>;

/** Price for a canonical id we ship a quote for; null otherwise (no live comp). */
function priceFor(canonicalId: string): WirePriceQuote | null {
  return canonicalId in PRICES ? PRICES[canonicalId as keyof typeof PRICES] : null;
}

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

// Pre-grade fixtures, mirroring apps/api's grading mock. The `estimated` case is the
// canonical surface-limited one (the raking-light pass couldn't fully read the holo):
// it exercises the widened range + the `limited` provenance + the amber caveat, which
// is the screen's whole reason for existing. The `retake` case is the refuse-to-grade
// path: a skewed, glared capture that we won't put a confident wrong number on.

/** A clean, gradeable capture → an 8–9 band with a surface-limited axis (default). */
export const PREGRADE_ESTIMATED: WirePregradeResponse = {
  status: "estimated",
  disclaimer: PREGRADE_DISCLAIMER,
  probability: { likely_low: 8, likely_high: 9, at_least: 9, p_at_least: 0.62 },
  sub_scores: [
    { axis: "centering", score: 9.0, confidence: 0.93 },
    { axis: "corners", score: 8.5, confidence: 0.81 },
    { axis: "edges", score: 8.8, confidence: 0.84 },
    // Low confidence → surfaces as `limited`; the holo couldn't be fully read.
    { axis: "surface", score: 7.0, confidence: 0.42 },
  ],
  confidence: 0.78,
  reasons: null,
};

/** A skewed/glared capture too poor to grade honestly → coaching, never a number. */
export const PREGRADE_RETAKE: WirePregradeResponse = {
  status: "retake",
  disclaimer: PREGRADE_DISCLAIMER,
  probability: null,
  sub_scores: null,
  confidence: null,
  reasons: [
    "The card is tilted — shoot straight down so the borders stay parallel.",
    "Glare across the holo is hiding the surface. Angle away from the light.",
  ],
};

/**
 * Map a capture ref to a pre-grade fixture, mirroring apps/api's grading mock keys.
 * A ref containing "retake" returns the refuse-to-grade path; everything else estimates.
 */
export function pregradeFixtureFor(captureRef: string): WirePregradeResponse {
  return captureRef.includes("retake") ? PREGRADE_RETAKE : PREGRADE_ESTIMATED;
}

// Authenticity fixtures, mirroring apps/api's authenticity mock. The five outcomes the
// screen has to render honestly: a reassuring read, a mixed read, the most adverse read
// (still "seek a professional", never "fake"), a refuse-to-screen poor capture, and a
// below-threshold card that simply isn't worth screening. `confidence` is read-quality
// (how clearly the card scanned) throughout — never verdict-certainty.

/** Clean read on a high-value card — no counterfeit indicators (the most reassuring band). */
export const AUTHENTICITY_STRONG: WireAuthenticityResponse = {
  status: "assessed",
  disclaimer: AUTHENTICITY_DISCLAIMER,
  assessment: {
    risk_band: "strong_signals",
    confidence: 0.91,
    signals: [
      {
        kind: "print_pattern",
        observation: "consistent",
        confidence: 0.94,
        detail: "The CMYK rosette under magnification matches our reference for the Origins Vault print run.",
      },
      {
        kind: "holo_signature",
        observation: "consistent",
        confidence: 0.88,
        detail: "Foil reflectance across both tilt angles tracks the reference holo for this set.",
      },
      {
        kind: "font_layout",
        observation: "consistent",
        confidence: 0.93,
        detail: "Typography, kerning, and the energy box align with the reference layout.",
      },
      {
        kind: "cardstock",
        observation: "consistent",
        confidence: 0.86,
        detail: "Edge texture and stock thickness read as period-correct.",
      },
      {
        kind: "catalog_existence",
        observation: "consistent",
        confidence: 0.99,
        detail: "Origins Vault 8/120 holo was printed — the set, number, and variant all exist.",
      },
    ],
    recommend_authentication: true,
    reference_value_eur: 289.0,
  },
  reasons: null,
};

/** Mixed/insufficient evidence — some signals couldn't be read, so the read stays open. */
export const AUTHENTICITY_INCONCLUSIVE: WireAuthenticityResponse = {
  status: "assessed",
  disclaimer: AUTHENTICITY_DISCLAIMER,
  assessment: {
    risk_band: "inconclusive",
    confidence: 0.54,
    signals: [
      {
        kind: "print_pattern",
        observation: "consistent",
        confidence: 0.71,
        detail: "The dot pattern reads as consistent where it could be resolved.",
      },
      {
        kind: "holo_signature",
        observation: "unreadable",
        confidence: 0.22,
        detail: "Glare on the holo left too little to compare against the reference.",
      },
      {
        kind: "font_layout",
        observation: "inconclusive",
        confidence: 0.49,
        detail: "Layout is close to reference, but the capture was too soft to be sure.",
      },
      {
        kind: "cardstock",
        observation: "consistent",
        confidence: 0.63,
        detail: "Edge cues look period-correct.",
      },
      {
        kind: "catalog_existence",
        observation: "consistent",
        confidence: 0.98,
        detail: "Wildgrowth 15/88 holo was printed — the variant exists.",
      },
    ],
    recommend_authentication: true,
    reference_value_eur: 61.4,
  },
  reasons: null,
};

/** Signals diverge from a genuine reference — the most adverse band; never "fake". */
export const AUTHENTICITY_ELEVATED: WireAuthenticityResponse = {
  status: "assessed",
  disclaimer: AUTHENTICITY_DISCLAIMER,
  assessment: {
    risk_band: "elevated_risk",
    confidence: 0.83,
    signals: [
      {
        kind: "print_pattern",
        observation: "deviation",
        confidence: 0.87,
        detail: "The dot pattern is coarser than our reference for the Origins Vault print run.",
      },
      {
        kind: "holo_signature",
        observation: "deviation",
        confidence: 0.79,
        detail: "Foil reflectance falls off differently from the reference holo across tilt.",
      },
      {
        kind: "font_layout",
        observation: "consistent",
        confidence: 0.84,
        detail: "Typography and layout match the reference — these are easy to copy well.",
      },
      {
        kind: "cardstock",
        observation: "inconclusive",
        confidence: 0.58,
        detail: "Stock thickness is borderline; the edge read wasn't decisive.",
      },
      {
        kind: "catalog_existence",
        observation: "consistent",
        confidence: 0.99,
        detail: "Origins Vault 12/120 holo was printed — the variant itself exists.",
      },
    ],
    recommend_authentication: true,
    reference_value_eur: 757.1,
  },
  reasons: null,
};

/** Capture too poor to read the signals honestly — refuse, coach, never a band. */
export const AUTHENTICITY_RETAKE: WireAuthenticityResponse = {
  status: "retake",
  disclaimer: AUTHENTICITY_DISCLAIMER,
  assessment: null,
  reasons: [
    "The print-pattern close-up is too soft — move in until the dots are crisp.",
    "Glare covers the holo. Tilt the card slowly so the foil catches light from the side.",
  ],
};

/** Below the value threshold — cheap commons aren't faked, so no score is offered. */
export const AUTHENTICITY_NOT_ASSESSED: WireAuthenticityResponse = {
  status: "not_assessed",
  disclaimer: AUTHENTICITY_DISCLAIMER,
  assessment: null,
  reasons: [
    "This card's market value is low enough that it isn't a target for forgery.",
    "Authenticity screening is reserved for higher-value cards, where a bad buy would cost you.",
  ],
};

/**
 * Map a capture ref to an authenticity fixture, mirroring apps/api's authenticity mock keys.
 * The ref carries which outcome the demo should exercise; on device the outcome is the
 * service's, keyed off the resolved card and capture, never the ref string.
 */
export function authenticityFixtureFor(captureRef: string): WireAuthenticityResponse {
  if (captureRef.includes("retake")) return AUTHENTICITY_RETAKE;
  if (captureRef.includes("not-assessed")) return AUTHENTICITY_NOT_ASSESSED;
  if (captureRef.includes("inconclusive")) return AUTHENTICITY_INCONCLUSIVE;
  if (captureRef.includes("elevated")) return AUTHENTICITY_ELEVATED;
  return AUTHENTICITY_STRONG;
}

// Stack / batch scan fixture — the realistic mixed pile rapid mode has to render
// honestly. It exercises every per-item outcome the review screen branches on:
//   • a resolved card the user flipped past *twice* (count 2 — the dedupe case)
//   • a second resolved card (count 1) for a bulk-add list with more than one row
//   • a needs_confirmation pair — the two Emberwyrm printings ~€733 apart, end-of-stack
//   • an unrecognized capture (a glared flip) the user can re-shoot
//   • a quota_exceeded item folding the captures the free tier's daily wall skipped
// The quota block tells the honest COGS story: 8/day limit, charged what was recognized,
// remaining 0, and the rejected count equal to the quota_exceeded item's count.

const UNRECOGNIZED_REF = "stack-cap-7";

export const STACK_BATCH: WireBatchScanResponse = {
  items: [
    {
      outcome: "resolved",
      count: 2,
      // The same card flipped past twice — both bundles deduped onto one entry.
      capture_refs: ["stack-cap-1", "stack-cap-4"],
      card: { identity: TIDECALLER_ORIGINS, confidence: 0.96, price: PRICES["origins-8"] },
      choices: null,
      price_delta: null,
    },
    {
      outcome: "resolved",
      count: 1,
      capture_refs: ["stack-cap-2"],
      card: { identity: GROVEKEEPER_WILDGROWTH, confidence: 0.94, price: PRICES["wild-15"] },
      choices: null,
      price_delta: null,
    },
    {
      outcome: "needs_confirmation",
      count: 1,
      capture_refs: ["stack-cap-3"],
      card: null,
      choices: [
        { identity: EMBERWYRM_ORIGINS, confidence: 0.6, price: PRICES["origins-12"] },
        { identity: EMBERWYRM_ECHO, confidence: 0.56, price: PRICES["echo-12"] },
      ],
      price_delta: "732.60",
    },
    {
      outcome: "unrecognized",
      count: 1,
      capture_refs: [UNRECOGNIZED_REF],
      card: null,
      choices: null,
      price_delta: null,
    },
    {
      outcome: "quota_exceeded",
      count: 2,
      capture_refs: ["stack-cap-9", "stack-cap-10"],
      card: null,
      choices: null,
      price_delta: null,
    },
  ],
  quota: { limit: 8, charged: 6, remaining: 0, rejected: 2 },
};

/** The stack fixture. On device the result is the service's, keyed off the real captures. */
export function batchScanFixture(): WireBatchScanResponse {
  return STACK_BATCH;
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
    price: PRICES["origins-8"],
  },
  {
    id: "fixture-grovekeeper",
    identity: GROVEKEEPER_WILDGROWTH,
    condition: "excellent",
    quantity: 2,
    acquired_price_eur: "44.00",
    price: PRICES["wild-15"],
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
    price: priceFor(canonicalId),
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

// Training consent, fixture-side. Off by default (the only honest default for personal data,
// charter §3.5). A consented scan/pre-grade bumps the matching count so the privacy screen's
// "N captures are helping improve Holofy" copy reflects the demo flow, and revoking clears it.
let consentedScans = 0;
let consentedPregrades = 0;
let consentedAuthenticity = 0;

function consentState(): WireConsentState {
  const granted = consentedScans + consentedPregrades + consentedAuthenticity > 0;
  return {
    granted,
    consented: {
      scans: consentedScans,
      pregrades: consentedPregrades,
      authenticity: consentedAuthenticity,
    },
  };
}

export function fixtureTrainingConsent(): WireConsentState {
  return consentState();
}

export function fixtureSetTrainingConsent(granted: boolean): WireConsentState {
  if (granted) {
    // Grant retroactively consents the existing demo captures so the count is non-zero.
    if (consentedScans === 0) consentedScans = 1;
  } else {
    consentedScans = 0;
    consentedPregrades = 0;
    consentedAuthenticity = 0;
  }
  return consentState();
}

/** Record a consented capture so the fixture's consent counts track the flow. */
export function fixtureNoteConsentedScan(): void {
  consentedScans += 1;
}

export function fixtureNoteConsentedPregrade(): void {
  consentedPregrades += 1;
}

export function fixtureNoteConsentedAuthenticity(): void {
  consentedAuthenticity += 1;
}

/** Reset mutable fixture state between tests/sessions. */
export function resetFixtures(): void {
  consentedScans = 0;
  consentedPregrades = 0;
  consentedAuthenticity = 0;
  collection = [
    {
      id: "fixture-tidecaller",
      identity: TIDECALLER_ORIGINS,
      condition: "near_mint",
      quantity: 1,
      acquired_price_eur: "210.00",
      price: PRICES["origins-8"],
    },
    {
      id: "fixture-grovekeeper",
      identity: GROVEKEEPER_WILDGROWTH,
      condition: "excellent",
      quantity: 2,
      acquired_price_eur: "44.00",
      price: PRICES["wild-15"],
    },
  ];
}
