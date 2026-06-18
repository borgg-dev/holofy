# ADR 0002 — Variant disambiguation: resolve by set symbol + collector number, gate on confidence

- **Status:** Accepted (build-approved). Captures Phase-0 Spike B.
- **Date:** 2026-06-18
- **Deciders:** ML/Backend lead (Spike B)
- **Relates to:** `docs/TECHNICAL_ARCHITECTURE.md` §3.1, the Phase-0 "SPIKE A/B"
  variant line in §7, and `docs/adr/0001-price-data-source.md` (the catalog this resolves
  against).

## Context

Holofy prices a card to the **specific variant**, because the spread between variants of
the *same named card* is catastrophic: Spike B enumerated **31 printings named exactly
"Charizard"** on the open catalog, ranging **€1.95 → €4,043 — a ×2,074 swing** (run output
in `spikes/variant_disambiguation/README.md`).

The trap is that **artwork and name cannot separate these rows.** TCGdex confirms the Base
Set (4/102), Base Set 2 (4/130), and Evolutions (11/108) Charizards all carry illustrator
Mitsuhiro Arita and the same flame pose — *identical artwork, ~3× price spread*. An image
embedding or name match lands on "Charizard" and is then free to be hundreds of times wrong
on value. Getting a high-value variant wrong is the named product-killer in the master plan:
it destroys portfolio accuracy and the trust the wedge depends on.

The hypothesis under test: the **printed set symbol + bottom-corner collector number**
("4/102") is the ground truth that resolves the variant, and an OCR + classify step can
recover it reliably enough — with a confidence gate for the cases it cannot.

## Options evaluated

### 1. Artwork / embedding match alone

- **Shape:** recognise the card by image similarity, price the top-1 match.
- **Reality:** ~97–98% top-1 *image* match (Ximilar-class) — but that is accuracy on the
  *name/art*, not the *variant*. On reprinted artwork it cannot, even in principle, choose
  between Base Set and Evolutions. **Rejected as the sole resolver** — it is the
  candidate-narrowing step, not the disambiguator.

### 2. Set symbol + collector-number OCR → resolve against catalog *(chosen)*

- **Shape:** after recognition narrows candidates, OCR the bottom-corner collector number
  and classify the set symbol from the high-res crop, then map `(set, collector №, variant)`
  to the canonical card in the reference DB. Spike B implements the resolution step against
  the live catalog.
- **Reality:** the collector number is the highest-signal field (set-unique within a name);
  OCR is ~98–99% on clean crops but **~80–90% on real phone photos**, degraded by glare on
  holo foil and vintage ink wear. Set-symbol classification cross-checks the implied set
  total ("/102" ⇒ Base era), which is more robust than symbol pixels alone in the
  near-identical WotC era. The two signals constrain each other.
- **Verdict:** **adopt.** Deterministic against the catalog, and the failure mode is a
  *weak read*, not a *wrong silent answer* — which option 3 converts into a safe outcome.

### 3. Confidence gate + top-2 with price delta *(adopted alongside 2)*

- **Shape:** when OCR + symbol agree with high confidence → confirm directly. When they
  read weakly or disagree → surface the **top-2 candidates with the € delta** and let the
  user pick ("Base Set 4/102 — €757, or Base Set 2 4/130 — €256?").
- **Verdict:** **adopt as a hard rule, not a fallback nicety.** It makes the expensive
  failure — confidently mispricing ×100 — structurally impossible, and the user's
  one-tap pick becomes a labelled training example (the moat).

## Decision

**Disambiguate variants deterministically by `(set symbol + collector number)` OCR/classify,
resolved against the ADR-0001 catalog. Never silently emit a high-value variant: gate on
read confidence and, when low, present the top-2 candidates with their € price delta for the
user to confirm.**

Engineering shape (consistent with `TECHNICAL_ARCHITECTURE.md` §3.1, §1.2 step 4):

- A `VariantResolver` over the reference DB: input is `(candidate names, OCR'd collector
  string, classified set hint, variant cues)`; output is a ranked list of canonical cards
  with confidence. Spike B's `enumerate_printings` is the embryonic catalog side.
- **Collector number is primary, set symbol corroborates.** Use the implied set total to
  separate same-number reprints; treat symbol pixels as a cross-check, not a sole signal.
- **The resolver returns a *ranked* result with confidence, always** — the UI decides
  auto-confirm vs top-2 prompt from that confidence, so the "never guess" rule lives in one
  place.
- **Carry language and within-card variant through.** Reverse-holo vs holo (priced
  separately by Cardmarket: `trend` vs `trend-holo`) shares the symbol and number and is
  *not* OCR-resolvable — resolve it from a foil cue or a user prompt, and price the matched
  sub-variant. Same for JP/KR/EN language printings.
- **Degrade honestly.** Total-less promos and alphanumeric numbers ("SWSH066/307",
  "TG03/196", "4A/25") must resolve on the bare string; no Cardmarket entry ⇒ "no recent
  sales", never €0 (consistent with ADR 0001).

## Consequences

**Positive**

- Closes the named ×10+ product-killer: the variant the user is priced on is the one their
  card actually is, or they were explicitly asked. Spike B quantifies the avoided error
  (×2,074 on one name).
- The confidence-gated confirm step doubles as the consented-label data loop — every weak
  case the user resolves trains the in-house model that later moves recognition on-device.
- Clean seam: the catalog side is proven and swappable; the read side (Ximilar OCR → own
  model) can be upgraded without touching the resolver contract.

**Negative / cost**

- **Accuracy is gated by capture quality.** Corner OCR on holo/vintage phone photos is the
  real ceiling — this makes the guided-capture quality gate a hard **[DEP: Design]**
  dependency (reject + coach a retake before reading a sub-threshold crop), the same
  capture↔ML handshake pre-grade depends on.
- The top-2 confirm step adds a tap on low-confidence scans — acceptable, and only when the
  € delta justifies interrupting the user.
- Reverse-vs-holo and language splits need a non-OCR signal; bounded, tracked gaps, not
  blockers.

**No new external blocker.** Unlike ADR 0001, this decision needs no key or legal gate to
build against — it runs on the same no-key catalog already proven. The dependency it raises
is internal: the Design guided-capture flow. Tracked in `BLOCKERS.md` under "Capture quality
gates disambiguation + pre-grade accuracy."

## References

- Spike B proof + live spread table — `spikes/variant_disambiguation/README.md`,
  `spikes/variant_disambiguation/FINDINGS.md`
- Ximilar Collectibles Recognition (set/number/variant attributes, ~97–98% match) —
  https://www.ximilar.com/blog/pokemon-card-image-search-engine/ ,
  https://docs.ximilar.com/collectibles/recognition
- OCR accuracy on printed digits vs phone-photo/glare conditions —
  https://www.extend.ai/resources/pytesseract-guide-ocr-limits-alternatives
- Set-symbol classification approaches and limits of image-only fine-variant ID —
  https://medium.com/image-classification-tutorials/accelerating-pokemon-tcg-automation-building-a-multi-modal-ai-card-recognition-api-6cb0c462c150
- Catalog this resolves against — `docs/adr/0001-price-data-source.md`
