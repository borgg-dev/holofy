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

/**
 * apps/api/app/schemas/cards.py :: CardGame — the game a card belongs to.
 * An open category sourced from recognition: a stable `id` slug plus a human `name`.
 * Not an enum — a new game arrives as data, and the client groups on it without a code
 * change.
 */
export type WireCardGame = {
  id: string;
  name: string;
};

/** apps/api/app/schemas/cards.py :: CardIdentity */
export type WireCardIdentity = {
  canonical_id: string;
  /** Which game this card belongs to — the Vault groups holdings by it. */
  game: WireCardGame;
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

// Authenticity: the private anti-counterfeit screening contract. Mirrors
// apps/api/app/schemas/authenticity.py field-for-field. The shape is the defamation
// guardrail (charter §3.5) encoded in *types* — the headline is a three-value risk band,
// never a boolean; the most adverse outcome is "elevated risk, seek professional
// authentication"; and a poor capture or a low-value card is a typed `retake` /
// `not_assessed`, never a confident wrong answer. There is no fake/genuine field anywhere.

/** apps/api/app/schemas/authenticity.py :: SignalKind. The five per-signal reads. */
export type WireSignalKind =
  | "print_pattern"
  | "holo_signature"
  | "font_layout"
  | "cardstock"
  | "catalog_existence";

/** apps/api/app/schemas/authenticity.py :: SignalObservation. A consistency, never a verdict. */
export type WireSignalObservation = "consistent" | "inconclusive" | "deviation" | "unreadable";

/** apps/api/app/schemas/authenticity.py :: RiskBand. A band, deliberately never a boolean. */
export type WireRiskBand = "strong_signals" | "inconclusive" | "elevated_risk";

/** apps/api/app/schemas/authenticity.py :: AuthenticityStatus. */
export type WireAuthenticityStatus = "assessed" | "retake" | "not_assessed";

/** apps/api/app/schemas/authenticity.py :: AuthenticitySignal. confidence is read-quality. */
export type WireAuthenticitySignal = {
  kind: WireSignalKind;
  observation: WireSignalObservation;
  /** 0–1 — how clearly *this signal* could be read, NOT how certain the verdict is. */
  confidence: number;
  detail: string;
};

/** apps/api/app/schemas/authenticity.py :: AuthenticityAssessment. value arrives as a string. */
export type WireAuthenticityAssessment = {
  risk_band: WireRiskBand;
  /** 0–1 mean read-confidence of the signals — evidence quality, NOT verdict-certainty. */
  confidence: number;
  signals: WireAuthenticitySignal[];
  recommend_authentication: boolean;
  reference_value_eur: number | null;
};

/** apps/api/app/schemas/authenticity.py :: AuthenticityRequest (request body for POST). */
export type WireAuthenticityRequest = {
  capture_ref: string;
  card_id: string;
};

/**
 * apps/api/app/schemas/authenticity.py :: AuthenticityResponse.
 * `status` keys the payload: `assessed` carries the band + signals + confidence;
 * `retake`/`not_assessed` carry human-facing `reasons`. `disclaimer` is always present.
 */
export type WireAuthenticityResponse = {
  status: WireAuthenticityStatus;
  disclaimer: string;
  assessment: WireAuthenticityAssessment | null;
  reasons: string[] | null;
};

// Training consent: the user's explicit, revocable grip on the data-loop moat
// (apps/api/app/schemas/consent.py). Separate from app-usage consent and off by default;
// the privacy screen reads and writes it.

/** apps/api/app/schemas/consent.py :: ConsentCounts. Per-kind tally of consented captures. */
export type WireConsentCounts = {
  scans: number;
  pregrades: number;
  authenticity: number;
};

/** apps/api/app/schemas/consent.py :: ConsentState. */
export type WireConsentState = {
  granted: boolean;
  consented: WireConsentCounts;
};

/** apps/api/app/schemas/consent.py :: ConsentUpdate (request body for PUT /consent/training). */
export type WireConsentUpdate = {
  granted: boolean;
  note?: string | null;
};

// Stack / batch scan: a pile of captures in, deduped per-card results out. Mirrors
// apps/api/app/schemas/batch_scan.py field-for-field. Stack mode is ID + value only —
// there is intentionally no grade/authenticity anywhere in this contract. Each item
// carries a `count` (how many captures deduped onto it) and the `capture_refs` that
// merged there; the response also reports how the day's scan budget was spent.

/** apps/api/app/schemas/batch_scan.py :: BatchItemOutcome. */
export type WireBatchItemOutcome =
  | "resolved"
  | "needs_confirmation"
  | "unrecognized"
  | "quota_exceeded";

/**
 * apps/api/app/schemas/batch_scan.py :: BatchScanItem. One deduped entry in a stack.
 * `outcome` keys the payload: `resolved` carries `card`; `needs_confirmation` carries
 * `choices` + `price_delta`; `unrecognized` / `quota_exceeded` carry neither.
 */
export type WireBatchScanItem = {
  outcome: WireBatchItemOutcome;
  /** ≥1 — captures that deduped onto a card, or every capture that hit the daily wall. */
  count: number;
  capture_refs: string[];
  card: WireScannedCard | null;
  choices: WireConfirmationChoice[] | null;
  price_delta: string | null;
};

/** apps/api/app/schemas/batch_scan.py :: BatchScanQuota. How the day's budget was applied. */
export type WireBatchScanQuota = {
  limit: number;
  /** Captures that consumed a unit — i.e. were recognized (the honest COGS of this batch). */
  charged: number;
  remaining: number;
  /** Captures the budget couldn't cover, skipped before recognition (the quota_exceeded count). */
  rejected: number;
};

/** apps/api/app/schemas/batch_scan.py :: BatchScanResponse. */
export type WireBatchScanResponse = {
  items: WireBatchScanItem[];
  quota: WireBatchScanQuota;
};

/** A capture bundle ref the client sends per detected card. apps/api :: CaptureBundleRef. */
export type WireBatchScanRequestItem = {
  bundle_id: string;
  image_count?: number;
};

/** apps/api/app/schemas/batch_scan.py :: BatchScanRequest (body for POST /scan/batch). */
export type WireBatchScanRequest = {
  items: WireBatchScanRequestItem[];
};

/** apps/api/app/schemas/captures.py :: CaptureUploadResponse (POST /captures). */
export type WireCaptureUploadResponse = {
  ref: string;
  image_count: number;
};

// Auth: password accounts + the session bearer. Mirrors apps/api/app/schemas/auth.py.

/** apps/api/app/schemas/auth.py :: AuthUser. */
export type WireAuthUser = {
  id: string;
  email: string;
};

/** apps/api/app/schemas/auth.py :: AuthTokenResponse (POST /auth/register|login). */
export type WireAuthTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: WireAuthUser;
};

/** apps/api/app/core/errors.py :: ErrorResponse envelope. */
export type WireErrorResponse = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};
