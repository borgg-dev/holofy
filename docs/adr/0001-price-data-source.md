# ADR 0001 — Pricing data source: Cardmarket € (primary) + TCGPlayer $ (secondary)

- **Status:** Proposed — pending legal sign-off (see Consequences)
- **Date:** 2026-06-18
- **Deciders:** Backend/data lead (Spike A)
- **Supersedes:** the open question in `docs/TECHNICAL_ARCHITECTURE.md` §4 and the
  Phase-0 "SPIKE C" line in §7.

## Context

Holofy's wedge is **Cardmarket-native € valuation** for the European vintage collector.
Pricing is therefore not a feature — it is the product thesis. We need a reliable,
legal, EU-appropriate source of Cardmarket EUR prices (primary) and TCGPlayer USD
(secondary toggle), keyed to a specific card *variant* (the ×10 price spread between a
1st-edition shadowless Charizard and an unlimited one makes variant-level pricing
mandatory, not nice-to-have).

The structural problem: **the two marketplaces whose prices we want both gate their own
APIs shut.**

- **Cardmarket** restricts API access to verified *commercial sellers*, requires manual
  approval, restricts *presenting* its prices without a prior written agreement, and is
  **currently not accepting new API applications** at all.
- **TCGPlayer** (eBay-owned since 2022) **stopped granting new API access in late 2024**
  ("We are no longer granting new API access at this time"), with reports of existing
  keys being deprecated. Applying today returns silence.

So a direct integration with either is not a path we can build the MVP on. The
hypothesis under test (Spike A) was whether **aggregator catalog APIs that already
surface those two price points** give us a workable indirect path.

## Options evaluated

### 1. TCGdex (open, no-key catalog + embedded pricing)

- **Shape:** `GET https://api.tcgdex.net/v2/{locale}/cards/{id}` returns the card with a
  `pricing` object embedding `cardmarket` (EUR: `trend`, `avg`, `low`, `avg1/7/30`, plus
  `*-holo` variants, `updated`, `idProduct`) and `tcgplayer` (USD, per print variant).
  Cardmarket refreshes daily, TCGPlayer hourly. **No API key, no published hard rate
  limit** (it asks you to cache rather than re-fetch).
- **Proven:** Spike A fetched Base Set Charizard (`base1-4`) live — `trend €757.10`,
  `avg30 €529.99`, dated to the prior day. Multilingual catalog (French "Dracaufeu",
  same EUR), which matches our FR→ES→IT→DE→EN localisation order.
- **ToS reality:** the database is **MIT-licensed**; the project carries the standard
  "not affiliated with Nintendo/TPC" disclaimer. **What it does *not* state** is the
  provenance of its Cardmarket numbers (the price-history repo says only "different
  sources") or any explicit grant to *redistribute Cardmarket prices commercially*. MIT
  covers the database schema/code; it does not, on its own, launder a third party's
  price-display rights. **This is the gap.**
- **Verdict:** excellent zero-friction primary *interface* and the spike target;
  unsuitable as a *sole* source of legal comfort given undocumented provenance.

### 2. Pokémon TCG API / Scrydex (self-serve, keyed, commercial tier)

- **Shape:** the long-standing pokemontcg.io API, now consolidated under **Scrydex**,
  returns catalog + `cardmarket` (EUR) and `tcgplayer` (USD) price blocks per card.
  Free/affordable self-serve tiers; Scrydex adds a paid commercial tier with an SLA.
- **ToS reality:** its terms state price data is **"for informational purposes only … no
  guarantees,"** one key per person/company. Scrydex names Cardmarket as a source, which
  is a stronger provenance story than TCGdex's silence — but still does not, in public
  terms, *explicitly* grant our commercial display. The paid tier is the right place to
  get that in writing.
- **Verdict:** the **redundant, SLA-backed feed** and the right counterparty to obtain a
  written commercial-display confirmation from. Requires a key + spend.

### 3. Cardmarket / TCGPlayer direct APIs

- **Reality:** both effectively closed to new developers (above). Cardmarket additionally
  forbids presenting prices without a written agreement; a v2 migration is in flight.
- **Verdict:** **not an MVP path.** Pursue Cardmarket *partner status* in parallel as a
  later upgrade that would let us drop the intermediary and price from the source.

### 4. eBay Browse / Marketplace Insights (sold comps)

- **Reality:** real developer access exists, but **Marketplace Insights** (the API that
  exposes *sold* prices) is access-gated and granted case-by-case via developer support.
  Browse covers active listings, not realised sales.
- **Verdict:** **out of scope for raw € valuation.** It is the right tool for
  **graded-slab** valuation post-MVP (a PSA 10 trades nothing like a raw card), which is
  already a Phase 4 item. Not part of this decision.

## Decision

**Adopt the indirect aggregator path. Primary feed: Scrydex (Pokémon TCG API).
Redundancy feed: TCGdex. Direct Cardmarket partnership: pursued in parallel, not
depended on.**

Rationale for that ordering, not the reverse:

1. **Provenance and accountability.** Scrydex names Cardmarket as a source and offers a
   contracted commercial tier — a counterparty we can get written commercial-display
   terms from. TCGdex is superb for a no-key spike and as a free second opinion, but its
   undocumented price provenance makes it unwise as the *sole legal basis*.
2. **Redundancy is a requirement, not a luxury.** A single feed disappearing must not
   take valuation down. We read both, prefer the primary, fall back on staleness or
   absence, and **persist our own daily price snapshots to Postgres** — which both
   de-risks feed loss and seeds the value-over-time history the retention loop needs.

Engineering shape (consistent with `TECHNICAL_ARCHITECTURE.md` §4):

- A `PricingProvider` interface; `ScrydexProvider` and `TcgdexProvider` implement it.
  The spike's `fetch_cardmarket_price` is the embryonic TCGdex implementation.
- **Never call these on the hot path.** Sync the catalog nightly into Postgres; refresh
  prices daily (long tail) / hourly (high-value), serve from Redis. Honours both
  TCGdex's "please cache" guidance and our latency/cost budget.
- **`trend` is the headline value, not `avg`.** Cardmarket's trend is its own smoothed
  guide price and what a collector sees on the listing; raw `avg` windows whipsaw on
  thin vintage volume (observed in the spike). Always render the `updated` timestamp;
  treat >36h as stale.
- **Variant-level pricing is mandatory.** Resolve to the specific variant (holo / 1st-ed
  / shadowless) before pricing; surface `*-holo` fields accordingly. Degrade honestly to
  "no recent Cardmarket sales" when a card carries no entry — never €0 or a guess.

## Consequences

**Positive**

- Unblocks the entire core scan loop with a proven, low-cost, EU-native € source today.
- Two independent feeds + our own snapshot history = no single point of failure.
- Clean seam to swap in a direct Cardmarket partnership later with zero app changes.

**Negative / cost**

- We inherit the aggregators' refresh cadence (Cardmarket daily) and coverage gaps;
  honest staleness/empty states are now a UX requirement.
- Scrydex commercial tier = an account + recurring spend (blocker, not blocker-to-build).
- We do **not** own the price relationship; a feed's terms could change.

**Legal sign-off still required (HARD LAUNCH GATE)**

This ADR settles the *technical* path. It does **not** clear the *commercial-display*
question, and we should be honest that we cannot from the outside:

1. Written confirmation from **Scrydex** that its commercial tier permits us to
   **display Cardmarket-sourced prices in a paid app**, *or* a legal opinion that
   aggregator-sourced display is defensible without it.
2. A standing decision on whether to invest in **Cardmarket partner/commercial-seller
   status** to price from the source and remove this dependency.
3. Confirmation our **price-attribution and "informational only, not investment advice"
   disclaimers** satisfy the providers' terms and consumer-protection expectations in DE
   first, then FR/UK/IT/ES.

Until (1) is answered, treat the aggregator path as **build-approved, display-pending**.
Tracked in `BLOCKERS.md` under "Price-data redistribution terms."

## References

- Cardmarket API access (commercial-seller gated, currently closed) —
  https://help.cardmarket.com/en/cardmarket-api , https://help.cardmarket.com/en/api-partnerships
- TCGPlayer API closed to new developers (eBay-owned) —
  https://docs.tcgplayer.com/docs/welcome , https://justtcg.com/blog/the-definitive-tcgplayer-api-alternative-for-developers-in-2025
- Pokémon TCG API / Scrydex (Cardmarket € + TCGPlayer $, "informational only" terms) —
  https://pokemontcg.io/ , https://dev.pokemontcg.io/terms , https://scrydex.com/docs
- TCGdex pricing integration, FAQ (no key, "please cache"), MIT-licensed price history —
  https://tcgdex.dev/markets-prices , https://tcgdex.dev/faq , https://github.com/tcgdex/price-history
- eBay Browse / Marketplace Insights (sold comps, access-gated) —
  https://developer.ebay.com/api-docs/buy/browse/overview.html , https://developer.ebay.com/api-docs/buy/marketplace-insights/static/overview.html
