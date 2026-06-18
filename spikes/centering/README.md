# Spike D — pre-grade centering prototype

Answers one question for Phase 0: **can we measure card centering at the pixel level,
in-house, accurately enough to be the headline pre-grade signal — without OpenCV or a
labelled dataset?**

Centering is the cheapest and most *mathematically honest* of the four PSA sub-grades:
it is a direct geometric measurement of where the printed frame sits inside the card,
not a learned guess. This spike measures the four border widths, reports the standard
collector `L/R` and `T/B` ratios, and maps the worse axis to a quality band shaped after
PSA centering tolerances — always as an **estimate with a confidence**, never a grade
(per `docs/TECHNICAL_ARCHITECTURE.md` §3.2 and the charter's honest-framing rule).

The detector is classic 1-D intensity-gradient profiling in pure numpy (Pillow only
decodes image files). No OpenCV — for a flat, deskewed scan this is both sufficient and
transparent enough to audit line by line.

## Run

```bash
cd spikes/centering
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements.txt

python cli.py path/to/card.png        # measure a real, flat, deskewed card scan
python cli.py --demo 48 32 45 45      # synthetic card at known L/R/T/B border widths
```

## Demo output

```
$ python cli.py --demo 48 32 45 45
Synthetic card — ground-truth borders (48, 32, 45, 45) (L/R (60, 40), T/B (50, 50))

Centering estimate (pre-grade, not a grade)
  Left-Right : 60/40   (borders 48px / 32px)
  Top-Bottom : 50/50   (borders 45px / 45px)
  Quality    : excellent
  Confidence : 100%
```

A faint border↔art transition (low-contrast frame, or a soft capture) keeps the ratio but
honestly lowers the confidence rather than overclaiming:

```
$ python cli.py --demo 40 40 40 40     # with a Δ20-luma border, confidence ≈ 27%
```

## How it works

1. **Outer edge** — collapse the image to per-row and per-column mean-intensity profiles;
   the card edge is the strongest rising/falling step against the background. Crop to the
   card. Falls back to the full frame if the card bleeds off-edge.
2. **Inner frame** — within the cropped card, scan inward from each side for the first
   strong intensity step (border colour → art). The two opposing widths per axis are the
   border measurements. A guard band keeps the outer edge from being mistaken for the
   frame; an absolute-contrast floor rejects full-bleed faces that have no inner frame.
3. **Ratios & band** — express each axis as the collector `hi/lo` split; classify the
   *worse* axis (the grader's gating factor) into a band; report a confidence from the
   weaker border's transition strength (measurement quality, independent of how good the
   centering is).

## Tests

```bash
python -m pytest -q
# 19 passed
```

Synthetic cards give exact ground-truth borders, so the geometry is pinned to the pixel
rather than eyeballed: a randomised 100-card sweep (varied offsets + sensor noise) recovers
every border width exactly. Coverage spans the band thresholds, worst-axis selection, the
confidence behaviour (off-centre = still confident; low-contrast = less confident), a real
PNG decode round-trip, and the full-bleed / too-small / wrong-shape error branches.

## What this is and isn't

- **Is:** evidence that accurate, defensible, in-house centering is cheap and runs on plain
  numpy — confirming the §3.2 "build centering immediately" call.
- **Isn't:** a grade, and not a rectifier. It measures *aligned* input; perspective, skew,
  glare and rounded corners on raw phone photos are out of scope and belong to the
  guided-capture flow that feeds this stage. See `FINDINGS.md` for the real-world limits
  and how this slots into the broader pre-grade model.
```
