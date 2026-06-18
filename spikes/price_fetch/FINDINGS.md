# Spike A — findings

**Question:** does a legal, reliable path to Cardmarket € (primary) + TCGPlayer $
(secondary) pricing exist for an EU commercial app, given both marketplaces' own APIs
are closed to new developers?

## Verdict

**A *technical* € path exists and is proven** (see `README.md` — real Base Set Charizard
trend €757.10, dated, no API key). **The *commercial-display* path is not yet legally
cleared.** Decision and reasoning in `docs/adr/0001-price-data-source.md`.

- **Technical confidence: high.** TCGdex serves Cardmarket EUR + TCGPlayer USD per card,
  no key, with per-source freshness timestamps. Pokémon TCG API / Scrydex provides the
  same data with an SLA and a paid commercial tier as the redundant feed. Two
  independent sources cover the wedge.
- **Legal confidence: medium-low, and it's the gating risk.** None of these aggregators
  publishes terms that *explicitly* grant commercial redistribution of Cardmarket's
  prices. We are relying on them holding rights we cannot verify from the outside.

## Residual risks / blockers (for `BLOCKERS.md`)

1. **Commercial-display rights are unconfirmed (legal sign-off).** TCGdex's data is
   MIT-licensed and it asks consumers to cache, but nothing in writing says we may
   *display Cardmarket prices commercially*. Cardmarket itself restricts presenting its
   prices without a written agreement. We need either (a) written confirmation from the
   primary aggregator (Scrydex) that their terms cover our commercial display, or (b) a
   legal read that aggregator-sourced display is defensible. **This is the hard launch
   gate, not a nice-to-have.**

2. **Provenance of TCGdex's Cardmarket numbers is undocumented.** The price-history repo
   only says "different sources." We should not make TCGdex the *sole* primary feed on
   that basis — hence the ADR pairs it with Scrydex (which states a Cardmarket source)
   and persists our own daily snapshots.

3. **Long-tail / unlisted coverage gap.** Some EX/Full-Art era cards carry no Cardmarket
   entry on these feeds (`PriceUnavailable`). The UI must degrade honestly ("no recent
   Cardmarket sales") rather than show €0 or a stale guess.

4. **Account/subscription needed to harden.** Scrydex's commercial tier requires a key +
   spend — an account/money blocker once we move past the free TCGdex proof.

## Does this invalidate a core assumption?

No plan-level fork. The master plan already assumes the indirect-aggregator path and
flags legal sign-off as required; this spike confirms the technical leg and sharpens the
legal ask. Proceed with build against the aggregator interface; treat commercial-display
sign-off as a launch gate, not a build blocker.
