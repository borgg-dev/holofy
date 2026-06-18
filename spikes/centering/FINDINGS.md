# Spike D — findings

**Question:** can we build the centering pre-grade signal in-house, accurately enough to
be the headline feature, on plain numpy (no OpenCV, no labelled dataset)?

## Verdict

**Yes, for aligned input — and it is genuinely cheap.** A pure-numpy 1-D gradient
profiler recovers border widths to the pixel on synthetic ground truth, converts them to
the collector `L/R` / `T/B` ratios, and bands the worse axis against PSA-style tolerances
with a calibrated confidence. This confirms the architecture's §3.2 call to **build
centering immediately** rather than buy it. The honest caveat is entirely about *input
quality*, not the math.

## Accuracy on synthetics

Synthetic cards (outer rectangle + inner art panel at chosen border widths) give exact
labels, so we measure true error, not agreement-with-another-AI.

| Scenario | Result |
|---|---|
| Perfectly centred (40/40) | 50/50 both axes, `pristine`, 100% confidence |
| Known L/R offset (48/32 px = 60/40) | recovered 60/40 exactly, `excellent` |
| Extreme (72/12 px = 86/14) | recovered 86/14 exactly, `severe` |
| **Randomised sweep, 400 cards, sensor noise sigma<=6** | **max border error = 0 px** |
| Low-contrast border (delta 20 luma) | ratio held; confidence honestly dropped to ~27% |

The geometry is bias-free: switching the boundary detector from `np.gradient` (half-pixel
centred bias) to a `np.diff` forward-difference with an explicit index convention removed
a systematic 1-px asymmetry that otherwise skewed every ratio. That bug-and-fix is the
core lesson — sub-pixel index conventions matter more than the detection method here.

## Known limits (the real-world gap)

The prototype assumes a **flat, deskewed, axis-aligned** card on a contrasting background.
Raw phone photos violate that, and these are out of scope by design — they belong to the
capture stage, not the measurement:

- **Perspective / skew.** A tilted card makes opposite borders unequal *as imaged* even
  when the card is perfectly centred — directly corrupting the ratio. Needs a deskew /
  homography rectification before this stage. This is the single biggest dependency.
- **Glare & holo hotspots.** Specular highlights inject false intensity steps the profiler
  can lock onto. Mitigations: multi-angle capture, robust (median) profiles, masking
  blown-out regions.
- **Rounded corners.** Real cards aren't sharp rectangles; corner radius biases an
  edge-from-extremes detector. Measure borders along the straight mid-runs of each edge,
  not the corners.
- **Full-bleed vs bordered.** Modern full-art / full-bleed cards have no inner frame to
  measure; the prototype already detects this (transition below the noise floor ->
  `CenteringError`) so we degrade honestly instead of inventing a ratio. Product must
  surface "centering not applicable for this card type."
- **Border-colour ambiguity.** Cards whose frame colour is close to the adjacent art give a
  faint transition; confidence drops, which is correct — but a learned border segmenter
  will eventually beat a single intensity threshold on these.

## How this feeds the broader pre-grade model

Centering is one of four PSA sub-grades. This stage emits a structured `CenteringResult`
(ratios + band + confidence + raw border pixels) that the pre-grade service combines with
bought corners/edges/surface scores (Ximilar initially, §3.2) into the overall
**grade-probability distribution** Product presents — never a single number. Two
properties make it the right first in-house brick:

1. **It is interpretable.** "55/45 L-R" is something a collector can verify by eye, which
   builds the trust the wedge depends on; a CNN score cannot be checked this way.
2. **It generates labels.** Stored alongside the eventual real PSA/CGC outcome, our exact
   centering measurement becomes a clean feature for the proprietary model — the moat loop
   in §3.2, fed by a signal we computed rather than rented.

## Capture-UX dependency (the hard [DEP: Design])

This algorithm is only as good as its input. It needs **flat, glare-free, deskewed,
fully-in-frame** capture — exactly the guided scan-frame Design owns. Concretely the
capture stage must hand off: a rectified (perspective-corrected) crop, a glare/blur
quality gate, and a flag for full-bleed card types. Without that, ratios will be wrong in
a way that *looks* precise — the most dangerous failure mode for an honesty-led product.
Recommend wiring the on-device deskew + quality gate before exposing centering to users.

## Does this invalidate a core assumption?

No. It confirms the plan: centering is cheap, defensible, and buildable now. The only new
sharpening is that **the capture/deskew dependency is a hard prerequisite, not a polish
item** — measurement accuracy is meaningless on unrectified input. Tracked for Design in
`BLOCKERS.md` terms as a Phase-2 prerequisite, not a Phase-2 nicety.
