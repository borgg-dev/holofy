// App-facing models — what screens and view-logic consume.
//
// The boundary with the wire layer is deliberate: money is a `number` in major units
// (euros, the unit ValueText formats), timestamps are `Date`, and the two scan outcomes
// are a discriminated union so a screen `switch`es on `outcome` and the compiler proves
// the right fields are present. Nothing here knows about HTTP.

import type { WireCondition, WireVariant } from "./types";

export type Variant = WireVariant;
export type Condition = WireCondition;

/**
 * The game a card belongs to, as carried on the card identity. This is an *open*
 * category: `id` is a stable slug from recognition (e.g. "pokemon", "one_piece"),
 * `name` its human label (e.g. "Pokémon", "One Piece"). The Vault groups on `id` and
 * labels on `name` — it never consults a fixed list of games, so a game scanned for the
 * first time gets its own section with no code change.
 */
export type CardGame = {
  /** Stable slug from recognition — the grouping key. */
  id: string;
  /** Nominative label shown in the Vault section header — e.g. "Pokémon". */
  name: string;
};

/**
 * The brand-color keys a game section can tint with. These are theme color *names*
 * (not literal hexes) so the chip resolves against the active scheme and reads right
 * in both light and dark. The Vault derives one of these from a game's id.
 */
export type GameAccent =
  | "vaultTeal"
  | "foilMagenta"
  | "holoViolet"
  | "amber"
  | "irisLavender"
  | "roseMagenta";

/**
 * A game's *display* presentation, derived deterministically from its identity — what
 * the Vault renders. Nothing here is authored per game: `accent` is hashed from the id
 * (stable across sessions), `initial` is the first letter of the name. `gameDisplay`
 * is the one place this derivation lives.
 */
export type GameDisplay = CardGame & {
  /** Single-letter mark for the generic glyph — never an official logo. */
  initial: string;
  /** Theme brand-color key the glyph and subtotal tint draw from. */
  accent: GameAccent;
};

// The accent palette a game's color is drawn from — on-brand keys that resolve against
// the theme. The id is hashed onto this list, so every game gets a stable, distinct-ish
// color with zero per-game configuration.
const ACCENT_PALETTE: readonly GameAccent[] = [
  "vaultTeal",
  "foilMagenta",
  "holoViolet",
  "amber",
  "irisLavender",
  "roseMagenta",
];

// Optional cosmetic curation: a hand-picked accent for flagship games, layered over the
// derived default. Purely a polish override — a game absent here still gets a proper
// derived color. No code path requires a game to appear in this map.
const CURATED_ACCENTS: Readonly<Record<string, GameAccent>> = {
  pokemon: "vaultTeal",
  lorcana: "foilMagenta",
};

// A small, stable string hash (FNV-1a + an xorshift finalizer). Deterministic across
// sessions and platforms; the finalizer avalanches the low bits so short ids spread
// across the palette instead of clustering on one slot under the modulo.
function hashId(id: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  h ^= h >>> 16;
  h = Math.imul(h, 0x21f0aaad);
  h ^= h >>> 15;
  h = Math.imul(h, 0x735a2d97);
  h ^= h >>> 15;
  return h >>> 0;
}

// The colors curation has claimed. An auto-derived game draws from the rest, so a brand-new
// game never collides with a flagship's hand-picked tint in the Vault.
const RESERVED = new Set(Object.values(CURATED_ACCENTS));
const DERIVED_PALETTE: readonly GameAccent[] = ACCENT_PALETTE.filter((a) => !RESERVED.has(a));

/**
 * The accent for a game id. A curated override wins; otherwise the id is hashed onto the
 * un-reserved palette, so every game — including one never seen before — gets a stable,
 * distinct color with no per-game code.
 */
export function gameAccent(id: string): GameAccent {
  const curated = CURATED_ACCENTS[id];
  if (curated) return curated;
  const palette = DERIVED_PALETTE.length > 0 ? DERIVED_PALETTE : ACCENT_PALETTE;
  return palette[hashId(id) % palette.length]!;
}

/** The first letter of a game's name, uppercased — the glyph mark. Falls back to "?". */
export function gameInitial(name: string): string {
  const ch = name.trim()[0];
  return ch ? ch.toUpperCase() : "?";
}

/**
 * Derive a game's full display from its identity. Pure and total — works for any game,
 * curated or not, so a never-before-seen game renders a proper section the first time
 * one of its cards is scanned.
 */
export function gameDisplay(game: CardGame): GameDisplay {
  return {
    id: game.id,
    name: game.name,
    initial: gameInitial(game.name),
    accent: gameAccent(game.id),
  };
}

// ── Auth ──────────────────────────────────────────────────────────────────────

/** The signed-in account the app holds onto — opaque id + login email. */
export type AuthAccount = {
  id: string;
  email: string;
};

/** A successful register/login: the bearer to send, when it expires, and who it's for. */
export type AuthSession = {
  token: string;
  /** Seconds until the token expires — used to pre-empt a stale-token call. */
  expiresInSeconds: number;
  user: AuthAccount;
};

/** What the sign-in form submits. */
export type Credentials = {
  email: string;
  password: string;
};

export type CardIdentity = {
  canonicalId: string;
  /** Which game this card belongs to — the Vault groups holdings by it. */
  game: CardGame;
  name: string;
  setName: string;
  /** Already in "12/120" form from recognition. */
  collectorNumber: string;
  /** ISO-639 code, e.g. "en", "de". */
  language: string;
  variant: Variant;
  /** Absolute URL of the card's real catalog artwork, or null when the catalog has none
   *  (the card hero falls back to the foil placeholder). */
  imageUrl: string | null;
};

export type PriceQuote = {
  canonicalId: string;
  currency: string;
  /** Major units (euros), or null for a long-tail card with no liquid comp. */
  value: number | null;
  /** The card's native US-market price (TCGplayer, USD major units), or null/absent when no USD
   *  market carries it. A real market quote shown for the USD view — not an FX conversion of
   *  `value`. Optional so a price built without it (fixtures, legacy) is still valid. */
  usdValue?: number | null;
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
  /** The condition the grade band implies (e.g. "light_played"), or null if not derived. */
  estimatedCondition: Condition | null;
  /** The near-mint guide value (EUR major units), and "your copy" — the guide scaled to the
   *  estimated condition. Null when the card wasn't priceable. Both estimates, shown together. */
  baselineValueEur: number | null;
  conditionAdjustedValueEur: number | null;
  disclaimer: string;
  /** Centering pre-grade is an in-house beta — the UI shows a "Beta" label so the estimate
   *  is never read as authoritative. */
  experimental: boolean;
};

/** Capture too poor to grade honestly: coaching reasons to re-capture, never a grade. */
export type PregradeRetake = {
  status: "retake";
  reasons: string[];
  disclaimer: string;
  experimental: boolean;
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
