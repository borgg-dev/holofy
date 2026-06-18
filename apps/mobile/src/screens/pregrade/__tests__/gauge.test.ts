import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  GAUGE,
  arcPath,
  confidencePercent,
  formatScore,
  gaugeA11y,
  gradeFraction,
  modalGrade,
  pointAtFraction,
  rangeLabel,
  subScoreA11y,
  subScoreValue,
  verdictFor,
  verdictLine,
} from "../gauge";
import type { GradeProbabilityRange, SubScore } from "@/api";

const band = (over: Partial<GradeProbabilityRange> = {}): GradeProbabilityRange => ({
  likelyLow: 8,
  likelyHigh: 9,
  atLeast: 9,
  pAtLeast: 0.62,
  ...over,
});

describe("verdictFor — never red, driven by p_at_least", () => {
  it("reads worth grading above the submission-worth probability", () => {
    assert.equal(verdictFor(band({ pAtLeast: 0.7 })).tone, "worth");
  });
  it("reads borderline in the middle band", () => {
    assert.equal(verdictFor(band({ pAtLeast: 0.45 })).tone, "borderline");
  });
  it("reads a calm hold-off below, never an alarm", () => {
    const v = verdictFor(band({ pAtLeast: 0.1 }));
    assert.equal(v.tone, "hold");
    assert.match(v.label, /hold/i);
  });
  it("only ever emits the three non-alarming tones", () => {
    for (const p of [0, 0.34, 0.35, 0.59, 0.6, 1]) {
      assert.ok(["worth", "borderline", "hold"].includes(verdictFor(band({ pAtLeast: p })).tone));
    }
  });
});

describe("range + verdict labels — a band, never a single grade", () => {
  it("formats a two-ended band", () => {
    assert.equal(rangeLabel(band({ likelyLow: 8, likelyHigh: 9 })), "8–9");
  });
  it("collapses a one-grade band to a single figure (still a range, not 'the grade')", () => {
    assert.equal(rangeLabel(band({ likelyLow: 9, likelyHigh: 9 })), "9");
  });
  it("reads the range and recommendation together", () => {
    const r = band({ pAtLeast: 0.7 });
    assert.equal(verdictLine(r, verdictFor(r)), "Likely 8–9 · Worth grading");
  });
});

describe("gauge geometry", () => {
  it("maps grade 1 to 0 and grade 10 to 1 along the sweep", () => {
    assert.equal(gradeFraction(1), 0);
    assert.equal(gradeFraction(10), 1);
  });
  it("clamps an out-of-range grade onto the arc rather than painting off it", () => {
    assert.equal(gradeFraction(0), 0);
    assert.equal(gradeFraction(12), 1);
  });
  it("places the endpoints level (the arc opens at the bottom, symmetric)", () => {
    const start = pointAtFraction(0);
    const end = pointAtFraction(1);
    assert.ok(Math.abs(start.y - end.y) < 0.5, "endpoints should sit at the same height");
    assert.ok(start.x < GAUGE.center.x && end.x > GAUGE.center.x, "1 left of center, 10 right");
  });
  it("puts the band midpoint at the modal grade", () => {
    assert.equal(modalGrade(band({ likelyLow: 8, likelyHigh: 9 })), 8.5);
  });
  it("emits a valid SVG arc command spanning the band", () => {
    const d = arcPath(8, 9);
    assert.match(d, /^M [\d.-]+ [\d.-]+ A 94 94 0 0 1 [\d.-]+ [\d.-]+$/);
  });
});

describe("score formatting — tabular, trimmed", () => {
  it("trims a whole score", () => {
    assert.equal(formatScore(9.0), "9");
  });
  it("keeps one decimal otherwise", () => {
    assert.equal(formatScore(8.5), "8.5");
  });
  it("hedges a limited axis value with a tilde", () => {
    const limited: SubScore = { axis: "surface", score: 7, confidence: 0.4, provenance: "limited" };
    assert.equal(subScoreValue(limited), "~7 / 10");
  });
  it("shows a measured axis value plainly", () => {
    const measured: SubScore = { axis: "centering", score: 9, confidence: 0.93, provenance: "measured" };
    assert.equal(subScoreValue(measured), "9 / 10");
  });
});

describe("accessibility strings — the real content is text", () => {
  it("announces the range, verdict, and confidence, never a single grade", () => {
    const r = band({ pAtLeast: 0.7 });
    const said = gaugeA11y(r, verdictFor(r), 0.85);
    assert.equal(
      said,
      "Pre-grade estimate: likely 8 to 9. Worth grading. Confidence: about 85 percent within one grade."
    );
  });
  it("announces a one-grade band without a spurious 'to'", () => {
    const r = band({ likelyLow: 9, likelyHigh: 9, pAtLeast: 0.7 });
    assert.match(gaugeA11y(r, verdictFor(r), 0.8), /likely 9\. Worth grading/);
  });
  it("announces each sub-score with value, max, and provenance", () => {
    const sub: SubScore = { axis: "centering", score: 9, confidence: 0.93, provenance: "measured" };
    assert.equal(subScoreA11y(sub), "Centering: 9 out of 10, measured.");
  });
  it("flags a limited axis as a limited assessment", () => {
    const sub: SubScore = { axis: "surface", score: 7, confidence: 0.4, provenance: "limited" };
    assert.match(subScoreA11y(sub), /limited assessment/);
  });
  it("rounds confidence to a whole percent", () => {
    assert.equal(confidencePercent(0.784), 78);
  });
});
