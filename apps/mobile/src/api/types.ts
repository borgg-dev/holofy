// The wire contract, mirrored from the FastAPI DTOs (apps/api/app/schemas).
// These are the *raw* JSON shapes — money arrives as strings (the backend serializes
// Decimal as a string so cents never round-trip through a float). The client maps these
// into the app-facing models in `models.ts`, where money is a number in major units and
// timestamps are Date. Screens consume the models, never these.

/** apps/api/app/schemas/cards.py :: Variant */
export type WireVariant = "normal" | "holo" | "reverse_holo" | "first_edition" | "promo";

/** apps/api/app/db/models/enums.py :: CardCondition */
export type WireCondition =
  | "mint"
  | "near_mint"
  | "excellent"
  | "good"
  | "light_played"
  | "played"
  | "poor";

/** apps/api/app/schemas/scan.py :: ScanOutcome */
export type WireScanOutcome = "resolved" | "needs_confirmation";

/** apps/api/app/schemas/cards.py :: CardIdentity */
export type WireCardIdentity = {
  canonical_id: string;
  name: string;
  set_name: string;
  collector_number: string;
  language: string;
  variant: WireVariant;
};

/** apps/api/app/schemas/cards.py :: PriceQuote. Decimal fields arrive as strings. */
export type WirePriceQuote = {
  canonical_id: string;
  currency: string;
  value: string | null;
  basis: string;
  low: string | null;
  avg30: string | null;
  source: string;
  as_of: string;
  age_hours: number;
  listing_url: string | null;
};

/** apps/api/app/schemas/scan.py :: ScannedCard */
export type WireScannedCard = {
  identity: WireCardIdentity;
  confidence: number;
  price: WirePriceQuote | null;
};

/** apps/api/app/schemas/scan.py :: ConfirmationChoice */
export type WireConfirmationChoice = {
  identity: WireCardIdentity;
  confidence: number;
  price: WirePriceQuote | null;
};

/** apps/api/app/schemas/scan.py :: ScanResponse */
export type WireScanResponse = {
  outcome: WireScanOutcome;
  card: WireScannedCard | null;
  choices: WireConfirmationChoice[] | null;
  price_delta: string | null;
};

/** apps/api/app/schemas/scan.py :: CaptureBundleRef (request body for POST /scan). */
export type WireCaptureBundleRef = {
  bundle_id: string;
  image_count: number;
};

// Collection + portfolio: these endpoints are being added server-side in parallel
// (apps/api/app/db/repositories/{collection,portfolio}.py back them). The wire shapes
// below follow the same conventions as the shipped scan contract — Decimal-as-string,
// snake_case, a card identity embedded — so the client's mapping needs no rework when
// the routes land.

/** A holding the user owns: a CollectionItem joined to its catalog card + current price. */
export type WireCollectionItem = {
  id: string;
  identity: WireCardIdentity;
  condition: WireCondition;
  quantity: number;
  acquired_price_eur: string | null;
  price: WirePriceQuote | null;
};

/** Request body for POST /collection. */
export type WireAddToCollection = {
  canonical_id: string;
  condition: WireCondition;
  quantity?: number;
  acquired_price_eur?: string | null;
};

/** apps/api/app/db/models/portfolio.py :: PortfolioSnapshot, the latest valuation. */
export type WirePortfolioSnapshot = {
  total_value_eur: string;
  total_cost_basis_eur: string | null;
  item_count: number;
  valuation_basis: string;
  captured_at: string;
};

/** GET /portfolio — the latest snapshot plus the prior one, for the change delta. */
export type WirePortfolio = {
  latest: WirePortfolioSnapshot;
  previous: WirePortfolioSnapshot | null;
};

// Pre-grade: the honest, probabilistic grading screen's contract. Mirrors
// apps/api/app/schemas/grading.py exactly. The deliberate shape — a range, not a
// number; a typed `retake` instead of a confident wrong answer — is load-bearing,
// so the wire types reproduce it field-for-field.

/** apps/api/app/schemas/grading.py :: GradingAxis. The four PSA sub-grades. */
export type WireGradingAxis = "centering" | "corners" | "edges" | "surface";

/** apps/api/app/schemas/grading.py :: PregradeStatus. */
export type WirePregradeStatus = "estimated" | "retake";

/** apps/api/app/schemas/grading.py :: SubScore. score 1–10, confidence 0–1. */
export type WireSubScore = {
  axis: WireGradingAxis;
  score: number;
  confidence: number;
};

/**
 * apps/api/app/schemas/grading.py :: GradeProbabilityRange.
 * A likely grade *band* plus P(grade ≥ at_least) — there is intentionally no
 * single `grade` field, and the client never synthesizes one.
 */
export type WireGradeProbabilityRange = {
  likely_low: number;
  likely_high: number;
  at_least: number;
  p_at_least: number;
};

/** apps/api/app/schemas/grading.py :: CaptureBundleRef-style request body. */
export type WirePregradeRequest = {
  capture_ref: string;
  card_id?: string | null;
};

/**
 * apps/api/app/schemas/grading.py :: PregradeResponse.
 * `status` keys the payload: `estimated` carries probability + sub_scores +
 * confidence; `retake` carries human-facing `reasons`. `disclaimer` is always present.
 */
export type WirePregradeResponse = {
  status: WirePregradeStatus;
  disclaimer: string;
  probability: WireGradeProbabilityRange | null;
  sub_scores: WireSubScore[] | null;
  confidence: number | null;
  reasons: string[] | null;
};

/** apps/api/app/core/errors.py :: ErrorResponse envelope. */
export type WireErrorResponse = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};
