# Spike B — findings

**Question:** does `(set symbol + collector-number OCR)` reliably disambiguate the
×N-price variants that an artwork/name match collapses together — and what accuracy can
we honestly expect from that OCR/classify step?

## Verdict

**The disambiguator is sound and the stakes are real.** The catalog side is *proven*:
31 distinct printings are named exactly "Charizard", spanning **€1.95 → €4,043 (×2,074)**,
and TCGdex confirms the **Base Set / Base Set 2 / Evolutions** printings share illustrator
Mitsuhiro Arita — identical artwork, ~3× price spread, separable only by the bottom number
and set symbol (see `README.md` for the live table). Name and artwork cannot pick the row;
the `(set, collector №, variant)` tuple can, deterministically, against the reference DB.

**The residual risk is entirely in the *reading* step, not the resolution step.** Whether
we recover "4/102" + the Base Set symbol correctly from a *phone photo of a 25-year-old
card* is the real variable, and it degrades under exactly the conditions vintage cards
present: glare on holo foil, soft corners, worn ink, off-angle capture.

## Accuracy expectation (set honestly)

The pipeline has two readable signals, and they are **complementary** — when one is weak
the other usually isn't, which is the whole reason to use both rather than either alone.

| Step | Realistic accuracy | Notes |
|---|---|---|
| **Artwork / name recognition** (narrows candidates) | ~97–98% top-1 image match (Ximilar-class) | Solved commodity; gets us to the right *name*, not the right *price*. |
| **Collector-number OCR** (the digits, e.g. "4/102") | ~98–99% on clean 300-DPI-equivalent crops; **~80–90% on real phone photos**, lower under glare/wear | The number is the highest-signal field — it is set-unique within a name. Glare on foil and worn vintage ink are the dominant failure modes. |
| **Set-symbol classification** (the era/set glyph) | High for a curated icon set via small CNN / icon-DB match; the long tail of near-identical symbols (Base era, the WotC reprints) is the hard part | Best used as a **cross-check** on the OCR'd set total, not a sole signal. |

**Combined, well-captured: high reliability.** The two signals constrain each other — the
collector number "4/102" *and* a Base-era symbol jointly pin the card; a disagreement is a
useful low-confidence signal rather than a silent error. The honest headline: **clean
capture resolves variants reliably; degraded capture is where we must not guess.**

## Recommended pipeline (the decision)

1. **Recognise** — artwork/embedding narrows to the candidate printings sharing a name
   (Ximilar first, on-device later).
2. **Read the ground truth** — OCR the bottom-corner collector number + classify the set
   symbol from the high-res crop. The number is primary; the symbol cross-checks the set
   total it implies ("/102" ⇒ Base-era).
3. **Resolve against the catalog** — map `(set, collector №, variant)` to the canonical
   card. This spike *is* a working model of this step.
4. **Gate on confidence, never silently guess a high-value variant.** When OCR + symbol
   agree with high confidence → confirm directly. When they disagree or read weakly →
   **show the top-2 candidates with the € delta** ("Base Set 4/102 — €757, or Base Set 2
   4/130 — €256?") and let the user pick. The price delta is what makes a one-tap
   confirmation worth the user's attention, and it converts our weakest case into a
   labelled training example (the moat).

This keeps the expensive failure — confidently mispricing a card ×100 — structurally
impossible: a low-confidence read degrades to a *cheap* user confirmation, not a *wrong*
silent answer.

## Residual risks / blockers (for `BLOCKERS.md`)

1. **Capture quality is the true accuracy ceiling.** OCR on phone photos of holo/vintage
   cards is the dominant failure mode (glare, wear, blur). This makes the guided-capture
   UX a hard **[DEP: Design]** dependency, not a nice-to-have — the quality gate must
   reject sub-threshold corner crops *before* we attempt to read them, and coach a
   reglare/refocus retake. Disambiguation accuracy is gated by capture, same as pre-grade.

2. **Near-identical set symbols in the WotC/Base era** — exactly the high-value era — are
   the hardest classification target. Mitigation: lean on the collector-number *total*
   ("/102" vs "/130" vs "/108" separates Base / Base Set 2 / Evolutions) as the primary
   set signal and treat the symbol as corroboration.

3. **Promos and number schemes vary** ("SWSH066/307", "TG03/196", "4A/25", bare promo
   numbers with no total). The OCR target isn't always a clean "N/M"; the resolver must
   handle alphanumeric and total-less collector strings (the spike's `set_code` already
   degrades to the bare number).

4. **Reverse-holo vs holo is a *within-card* variant**, priced separately by Cardmarket
   (`trend` vs `trend-holo`; e.g. Secret Wonders Charizard €70.53 holo vs €38.70 reverse).
   The set symbol + number are *identical* for both, so this last split is not resolved by
   OCR at all — it needs a foil-pattern visual cue or a user prompt. This is a known,
   bounded gap to flag in the disambiguation UX, not a blocker.

5. **Language/region printings** share a number but differ in price and authenticity
   profile (JP/KR/EN). The reference catalog is multilingual (Spike A); recognition must
   carry language through to the resolve step.

## Does this invalidate a core assumption?

No plan-level fork. The master plan and architecture (§3.1) already prescribe exactly this
approach — deterministic disambiguation by set symbol + bottom number, with a top-2 +
price-delta confirmation when confidence is low. This spike **confirms** the resolution
step works against a real catalog and **quantifies the stakes** (×2,074 on one name), and
sharpens the real ask: the accuracy budget lives in capture quality and corner OCR, so the
guided-capture UX and a confidence-gated confirm step are non-negotiable. Proceed to build
against this pipeline.

## Sources

- Ximilar Collectibles Recognition — reverse-search ~97%+ exact image match, ~98%+ TCG
  identification; returns set/number/variant attributes —
  https://www.ximilar.com/blog/pokemon-card-image-search-engine/ ,
  https://docs.ximilar.com/collectibles/recognition
- Tesseract OCR accuracy: ~98–99% clean printed text at 300 DPI, ~80–90% on phone photos,
  degraded by glare/uneven lighting —
  https://www.extend.ai/resources/pytesseract-guide-ocr-limits-alternatives ,
  https://www.bomberbot.com/ocr/how-to-use-image-preprocessing-to-improve-the-accuracy-of-tesseract-ocr/
- Set-symbol classification via small image model / icon-DB match, and the limits of
  image-only classification for fine variants —
  https://medium.com/image-classification-tutorials/accelerating-pokemon-tcg-automation-building-a-multi-modal-ai-card-recognition-api-6cb0c462c150
