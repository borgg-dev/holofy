// App-facing models — what screens and view-logic consume.
//
// The boundary with the wire layer is deliberate: money is a `number` in major units
// (euros, the unit ValueText formats), timestamps are `Date`, and the two scan outcomes
// are a discriminated union so a screen `switch`es on `outcome` and the compiler proves
// the right fields are present. Nothing here knows about HTTP.

import type { WireCondition, WireGameId, WireVariant } from "./types";

export type Variant = WireVariant;
export type Condition = WireCondition;

/** The TCGs Holofy catalogs. New games slot in here and in the GAMES registry below. */
export type GameId = WireGameId;

/**
 * A trading-card game as a first-class catalog entity. `accent` is a theme brand-color
 * *key* (not a literal hex) so the Vault's per-game glyph stays token-driven and reads
 * right in both light and dark — the screen resolves it against the active theme.
 */
export type Game = {
  id: GameId;
  /** Nominative label shown in the Vault section header — e.g. "Pokémon". */
  name: string;
  /** Single-letter mark for the generic glyph — never an official logo. */
  initial: string;
  /** Theme brand-color key the glyph and subtotal tint draw from. */
  accent: "holoViolet" | "vaultTeal" | "foilMagenta" | "amber";
};

// The game registry — the one place a TCG is described. Labels are nominative (fair use);
// the glyph mark is an original initial chip, never the game's logo. Accents are pulled
// from the existing brand palette so two games never introduce an off-system colour.
export const GAMES: Record<GameId, Game> = {
  pokemon: { id: "pokemon", name: "Pokémon", initial: "P", accent: "vaultTeal" },
  lorcana: { id: "lorcana", name: "Lorcana", initial: "L", accent: "foilMagenta" },
};

/** The game a card belongs to, with a defensive fallback if the registry ever lags the wire. */
export function gameOf(id: GameId): Game {
  return GAMES[id] ?? GAMES.pokemon;
}

export type CardIdentity = {
  canonicalId: string;
  /** Which TCG this card belongs to — the Vault groups holdings by it. */
  game: GameId;
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

// ── Stack / batch scan ───────────────────────────────────────────────────────
//
// Rapid mode's contract, app-side. The user flips through a pile while the client
// samples a bundle per detected card; the batch comes back as one deduped entry per
// card. It is **ID + value only** — there is no grade or authenticity in this shape,
// by design (master plan §7). Each item is a discriminated union so the review screen
// `switch`es on `outcome` and the compiler proves the right fields are present.
//
// `count` is how many captures collapsed onto a card (≥1) — the quantity the review
// pre-fills; `captureRefs` are the flips that merged there, in arrival order.

/** A confidently identified, priced card in a stack — review's bulk-add happy path. */
export type BatchResolved = {
  outcome: "resolved";
  count: number;
  captureRefs: string[];
  identity: CardIdentity;
  confidence: number;
  price: PriceQuote | null;
};

/** Two close variants whose € values diverge — confirmed at end of stack, never mid-flip. */
export type BatchNeedsConfirmation = {
  outcome: "needs_confirmation";
  count: number;
  captureRefs: string[];
  choices: ScanChoice[];
  /** Absolute € gap between the two choices, when both are priced. */
  priceDelta: number | null;
};

/** No card read from these captures — surfaced so the user can re-capture them. */
export type BatchUnrecognized = {
  outcome: "unrecognized";
  count: number;
  captureRefs: string[];
};

/** Captures past the day's scan budget — skipped before recognition, so no value was lost. */
export type BatchQuotaExceeded = {
  outcome: "quota_exceeded";
  count: number;
  captureRefs: string[];
};

export type BatchScanItem =
  | BatchResolved
  | BatchNeedsConfirmation
  | BatchUnrecognized
  | BatchQuotaExceeded;

/** How the day's scan budget was spent on a batch — the free tier's honest COGS picture. */
export type BatchQuota = {
  limit: number;
  charged: number;
  remaining: number;
  rejected: number;
};

export type BatchScan = {
  items: BatchScanItem[];
  quota: BatchQuota;
};

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

// ── Authenticity ─────────────────────────────────────────────────────────────
//
// The anti-counterfeit screening contract, app-side. The headline is a *risk band* —
// strongSignals / inconclusive / elevatedRisk — never a fake/genuine boolean (charter
// §3.5). The most adverse outcome is "elevated risk, seek professional authentication".
//
// `confidence` here is the *evidence quality* — the mean read-confidence of the signals,
// how clearly the card could be read — and is NOT verdict-certainty. A risky card can read
// at high confidence. The view-logic (band.ts) keeps it visually separate from the band so
// the UI never renders it as "X% sure it's risky". A capture too poor to read is a typed
// `retake`; a card below the value threshold is `notAssessed` — discriminated states, not a
// confident wrong answer, so a screen switches on `status` and the compiler proves the shape.

export type SignalKind =
  | "print_pattern"
  | "holo_signature"
  | "font_layout"
  | "cardstock"
  | "catalog_existence";

/** What one signal read says — a *consistency* with a genuine reference, never a verdict. */
export type SignalObservation = "consistent" | "inconclusive" | "deviation" | "unreadable";

/** The composite read. A band, never a boolean; the most adverse is `elevatedRisk`. */
export type RiskBand = "strongSignals" | "inconclusive" | "elevatedRisk";

export type AuthenticitySignal = {
  kind: SignalKind;
  observation: SignalObservation;
  /** 0–1 — how clearly *this signal* was read (capture/model quality). Not verdict-certainty. */
  confidence: number;
  /** Human-facing note on what was looked at — never an accusation. */
  detail: string;
};

/** Capture good enough to screen: the band, the per-signal reads, and the evidence quality. */
export type AuthenticityAssessment = {
  status: "assessed";
  band: RiskBand;
  /** 0–1 mean read-confidence across the signals — evidence quality, kept separate from the band. */
  confidence: number;
  signals: AuthenticitySignal[];
  /** Above the value threshold, the actionable output: a prompt to seek a professional. */
  recommendAuthentication: boolean;
  /** The € value that put the card over the screening threshold, for legible framing. */
  referenceValueEur: number | null;
  disclaimer: string;
};

/** Capture too poor to read the signals honestly: coaching reasons, never a band. */
export type AuthenticityRetake = {
  status: "retake";
  reasons: string[];
  disclaimer: string;
};

/** Below the value threshold — cheap commons aren't faked, so no score is offered. */
export type AuthenticityNotAssessed = {
  status: "notAssessed";
  reasons: string[];
  disclaimer: string;
};

export type Authenticity =
  | AuthenticityAssessment
  | AuthenticityRetake
  | AuthenticityNotAssessed;

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
