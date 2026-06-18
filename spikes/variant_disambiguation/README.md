# Spike B — variant disambiguation proof

Answers one question for Phase 0: **does the `(set, collector number, variant)` tuple
reliably resolve the ×N price spread between printings that share a name (and often the
exact artwork) — proving that name/art matching alone cannot price a card?**

The script enumerates every printing TCGdex catalogs under one exact name, resolves each
to its variant tuple plus Cardmarket € trend price, and prints the spread. It reuses the
no-key TCGdex path proven in [Spike A](../price_fetch/) and the decision in
[`docs/adr/0002-variant-disambiguation.md`](../../docs/adr/0002-variant-disambiguation.md).

## Why this matters

Mitsuhiro Arita's Base Set Charizard artwork was reprinted **unchanged** into Base Set 2
and Evolutions. An artwork embedding or a name match lands on "Charizard" and is then
free to be ~2000× wrong on value. The only thing that separates a €4,043 Skyridge holo
from a €1.95 McDonald's promo is the **set symbol + the printed collector number**
("4/102") — the exact targets a corner OCR + set-symbol classifier recovers.

## Run

```bash
cd spikes/variant_disambiguation
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt

python variant_spread.py                  # defaults to Charizard
python variant_spread.py Blastoise
python variant_spread.py Charizard --limit 5 --locale fr
```

`--limit` caps the per-printing detail fetches (the list endpoint omits pricing, so each
printing costs one follow-up call). Names use TCGdex's exact `eq:` filter, which excludes
near-name decoys ("Dark Charizard", "Blaine's Charizard") — those are a *recognition*
concern, not a *variant* one.

## Real output (captured 2026-06-18)

```
$ python variant_spread.py
Distinct printings named "Charizard" — same name, often the same artwork, resolved by (set, collector №, variant):

  VARIANT TUPLE                                     € TREND   ×vs floor
  ---------------------------------------------- ----------   ---------
  Skyridge 146/144 · Holo                         €4,043.40       ×2074
  Base Set 4/102 · 1st Edition                      €757.10        ×388
  Dragon 100/97 · Normal                            €629.09        ×323
  Plasma Storm 136/135 · Normal                     €577.97        ×296
  Expedition Base Set 6/165 · Holo                  €387.27        ×199
  Base Set 2 4/130 · Holo                           €255.57        ×131
  Evolutions 11/108 · Normal                        €238.85        ×122
  Legendary Collection 3/110 · Holo                 €232.13        ×119
  ...
  Pokémon GO 010/78 · Holo                            €4.39          ×2
  Vivid Voltage 25/185 · Reverse Holo                 €2.02          ×1
  McDonald's Collection 2024 1/15 · Normal            €1.95          ×1
  Genetic Apex 035/226 · Normal                  no Cardmarket data           —

Price spread: €1.95 → €4,043.40  =  ×2,074 swing on the same name.
Artwork/name match alone cannot pick the right row. The collector number + set symbol can — that is the disambiguator.
```

(Full run lists all 31 exact-name printings; trimmed here for readability.) The three
rows that make the point hardest are **Base Set 4/102 (€757), Base Set 2 4/130 (€256), and
Evolutions 11/108 (€239)** — TCGdex confirms all three carry illustrator *Mitsuhiro Arita*
and the same flame pose. Identical art, three sets, ~3× spread before you even reach the
Skyridge outlier. The disambiguator is the bottom number and the set symbol, nothing else.

Unknown names exit `2`; upstream failures exit `1`:

```
$ python variant_spread.py Mewthree
No card named 'Mewthree' in the catalog.   # exit 2
```

## What this is and isn't

- **Is:** evidence that the variant tuple resolves a real, catastrophic price spread, and
  a working model of the catalog-side resolution step the production pipeline performs.
- **Isn't:** the recognition pipeline itself. Production narrows candidates by artwork
  (Ximilar/on-device), reads the collector number + set symbol from the photo (OCR +
  classifier), resolves against this catalog, and — when confidence is low — shows the
  user the top-2 candidates **with the € delta** so they confirm. The accuracy of that
  OCR/classify step, and where it can still fail, is in
  [`FINDINGS.md`](./FINDINGS.md).
- It also intentionally degrades to "no Cardmarket data" for printings the feed doesn't
  price (Pocket-era cards, some promos), the same honest-empty posture Spike A took.
