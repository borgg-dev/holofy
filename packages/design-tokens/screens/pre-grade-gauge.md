# Signature screen — Pre-grade gauge (range + sub-scores)

The differentiator. After a guided multi-angle capture, the collector sees an honest answer to "is this worth sending to PSA?" — expressed as a **grade probability range**, never a single number, with four sub-scores and a plain-language verdict. Every pixel here is constrained by the product's legal and trust posture (master plan §6, charter §3.1): probabilistic, explainable, disclaimed.

The wow is the **gauge**: a 1–10 arc where the predicted range is painted as a luminous band (not a needle pointing at one value), so the uncertainty is the message. It should feel like a confident instrument that's honest about its limits.

---

## Layout

1. **Verdict header** — `overline` `PRE-GRADE ESTIMATE`, then `displayMd` verdict line: e.g. `Likely 8–9 · Worth grading`. The range and the recommendation read together.
2. **Gauge** — a 200° arc spanning 1–10, ticks at each integer with 10 emphasized. The predicted band (e.g. 8.0–9.0) is filled with a soft violet→teal gradient and a brighter core at the modal grade. Confidence shown as band edge softness + a `caption` `~85% within ±1 grade`.
3. **Sub-scores** — four rows: Centering · Corners · Edges · Surface. Each: label, a thin horizontal meter (0–10), and a `bodySm` value. Centering is marked `measured` (we build it in-house, pixel-level); the other three `estimated` (bought initially) — the provenance is shown, per the architecture.
4. **Surface caveat** — if the raking-light pass was incomplete, an inline `color.support.amber` note: `Surface limited — couldn't fully assess holo under raking light`.
5. **Disclaimer** — persistent footer, `caption` `color.semantic.dark.textTertiary`: `A pre-screen, not a grade. Not affiliated with PSA, CGC, or any grading service. Final grades may differ.`
6. **Actions** — `Log my real grade later` (feeds the data moat — consent-gated), `See what affects this`.

---

## Tokens used

- Background: `color.semantic.dark.bg`.
- Gauge track: `color.neutral.300`; ticks `color.neutral.400`, the `10` tick `color.semantic.dark.textSecondary`.
- Predicted band: linear `color.violet.500`→`color.teal.400`, modal core brightened; soft outer blur conveys confidence.
- Sub-score meter fill: `color.semantic.dark.accent`; track `color.neutral.200`. A meter in the weak zone (<5) tints toward `color.support.amber` past its midpoint — informative, not alarming.
- `measured` tag: teal `caption`; `estimated` tag: `color.neutral.600` `caption`.
- Verdict positive (`Worth grading`): `color.teal.400` glyph; marginal (`Borderline`): `color.support.amber`; not-worth: neutral, never red.
- Disclaimer: `caption`, `textTertiary` — always present, never dismissible.

---

## Motion choreography

| Step | Motion | Duration · easing |
|------|--------|-------------------|
| Gauge enter | arc draws clockwise 1→10 | `slow` `entrance` |
| Band reveal | predicted band fades + the modal core blooms | `base` `entrance`, after arc |
| Sub-scores | meters fill left→right, staggered 60ms top→bottom | `base` `standard` |
| Range label | the `8–9` counts/settles into place | `base` `spring` |
| Confidence text | fades in last | `fast` `standard` |

No celebratory foil here — this is the trust screen; foil would undercut the gravity of a grading decision. The only flourish is the band bloom.

`prefers-reduced-motion`: arc, band, and meters render in final state immediately; no draw or fill animation. Confidence and provenance still fully legible.

---

## States

- **Result** — full gauge + sub-scores + verdict as above.
- **Computing** — gauge track present, band area is a soft pulsing skeleton, sub-score meters are skeleton bars, header reads `Assessing four factors…`. Honest staged copy, no fake progress bar.
- **Capture insufficient** — if multi-angle/raking pass didn't meet threshold, the screen does **not** fabricate a grade: `displayMd` `Need a cleaner multi-angle scan to grade this`, body explaining which angle, button `Re-scan for grading`. This enforces §7.2 (refuse to grade sub-threshold photos).
- **Surface-blind** — full result but Surface sub-score shows `Limited` with the amber caveat and a slightly widened range to reflect the added uncertainty. Transparency over false precision.
- **Out of credits** — gauge teased blurred behind a `Pre-grade · 1 credit` paywall sheet; free tier shows remaining `2 of 3 this month`. Quota honored (charter §3.1).
- **Error** — model/network failure: `Couldn't complete the assessment` + `Try again`; credit is not consumed on failure.

---

## Accessibility

- The gauge is decorative reinforcement; the real content is text. SR reads: `Pre-grade estimate: likely 8 to 9. Worth grading. Confidence: about 85 percent within one grade.`
- Each sub-score announces value, max, and provenance: `Centering: 9 out of 10, measured. Surface: limited assessment.`
- The disclaimer is in the reading order near the verdict, not buried — it is part of the honest claim, not fine print to skip.
- Band/verdict color always paired with words (`Worth grading`, `Borderline`) — never color-only.
- Meters use `role="meter"` with `aria-valuenow`/`aria-valuemax`. Contrast AA throughout; amber-on-dark caveats meet AA at `caption` size.
