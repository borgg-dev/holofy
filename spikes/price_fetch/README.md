# Spike A — price-fetch proof

Answers one question for Phase 0: **can we read a Cardmarket EUR price for a specific
card, with a freshness timestamp, without holding a Cardmarket or TCGPlayer API key?**

The script resolves a [TCGdex](https://tcgdex.dev) catalog id to its embedded
Cardmarket pricing and prints the value, the trailing averages, and provenance.
TCGdex requires no key and surfaces Cardmarket EUR + TCGPlayer USD price points in the
same card object — this is the indirect path proposed in `docs/adr/0001-price-data-source.md`.

## Run

```bash
cd spikes/price_fetch
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt

python tcgdex_prices.py                 # defaults to base1-4 (Base Set Charizard 4/102)
python tcgdex_prices.py base1-4 --locale fr
```

Card ids follow TCGdex's `<set>-<localId>` scheme. Base Set Charizard is `base1-4`.
Find others at <https://api.tcgdex.net/v2/en/sets>.

## Real output (captured 2026-06-18)

```
$ python tcgdex_prices.py
Charizard  (base1-4)
  Cardmarket value : €757.10  [trend]
  30-day average   : €529.99
  lowest available : €100.00
  provenance       : Cardmarket EUR, via TCGdex catalog (en)
  freshness        : updated 2026-06-17T22:58:39.949000+00:00 (10h old)
  source listing   : https://www.cardmarket.com/en/Pokemon/Products/Singles?idProduct=273699
```

Localised catalog, identical EUR price — the wedge audience scans in French and still
prices in € (note the `avg7` window was distorted that day by a thin-volume spike, which
is exactly why we lead with `trend`, not `avg`):

```
$ python tcgdex_prices.py base1-4 --locale fr
Dracaufeu  (base1-4)
  Cardmarket value : €757.10  [trend]
  ...
  provenance       : Cardmarket EUR, via TCGdex catalog (fr)
```

Error paths exit with distinct codes (`2` not found, `3` no pricing, `1` upstream):

```
$ python tcgdex_prices.py nope-999
No catalog entry for 'nope-999'.   # exit 2
```

## What this is and isn't

- **Is:** evidence that a no-auth EUR price path exists and returns dated, attributable
  values for the exact wedge card.
- **Isn't:** the production pricing service. Production syncs the catalog nightly into
  Postgres and serves from a Redis cache (per the architecture doc §4) — never this
  endpoint on the hot path. TCGdex asks consumers to cache rather than re-fetch, and our
  daily snapshots also build the price history that de-risks any single feed vanishing.

The freshness field is load-bearing, not cosmetic: Cardmarket data on TCGdex refreshes
daily, so we display the update timestamp and treat anything older than ~36h as stale.
The unresolved commercial-display question is tracked in `FINDINGS.md` and `BLOCKERS.md`.
