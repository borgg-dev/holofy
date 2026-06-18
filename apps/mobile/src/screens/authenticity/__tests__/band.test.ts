import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  bandPresentation,
  evidenceQuality,
  evidenceQualityLine,
  signalA11y,
  signalRead,
  verdictA11y,
} from "../band";
import type { AuthenticityAssessment, AuthenticitySignal, RiskBand } from "@/api";

const ALL_BANDS: RiskBand[] = ["strongSignals", "inconclusive", "elevatedRisk"];

const signal = (over: Partial<AuthenticitySignal> = {}): AuthenticitySignal => ({
  kind: "print_pattern",
  observation: "consistent",
  confidence: 0.9,
  detail: "The dot pattern matches the reference print run.",
  ...over,
});

const assessment = (over: Partial<AuthenticityAssessment> = {}): AuthenticityAssessment => ({
  status: "assessed",
  band: "strongSignals",
  confidence: 0.9,
  signals: [signal()],
  recommendAuthentication: true,
  referenceValueEur: 289,
  disclaimer: "Private authenticity screening, not a verdict.",
  ...over,
});

describe("bandPresentation — never red, never a fake/genuine verdict", () => {
  it("maps strongSignals to a reassuring tone, hedged as 'no indicators', never asserting genuine", () => {
    const p = bandPresentation("strongSignals");
    assert.equal(p.tone, "reassuring");
    // The headline is the sanctioned "no counterfeit indicators" (master plan §6) — a
    // negation, never a positive "genuine"/"authentic" claim about the card.
    assert.doesNotMatch(p.headline.toLowerCase(), /\bgenuine\b/);
    assert.doesNotMatch(p.summary.toLowerCase(), /\bgenuine\b/);
    // The reassurance is explicitly not a guarantee/certificate.
    assert.match(p.summary.toLowerCase(), /not a guarantee/);
  });

  it("maps elevatedRisk to caution (amber), recommending a professional — never 'fake'", () => {
    const p = bandPresentation("elevatedRisk");
    assert.equal(p.tone, "caution");
    assert.match(p.summary.toLowerCase(), /professional authentication/);
    assert.doesNotMatch(p.headline.toLowerCase(), /fake|counterfeit/);
    assert.doesNotMatch(p.summary.toLowerCase(), /fake|counterfeit/);
  });

  it("maps inconclusive to caution, not an alarm", () => {
    assert.equal(bandPresentation("inconclusive").tone, "caution");
  });

  it("only ever emits the two non-alarming tones (no red/error tone exists)", () => {
    for (const band of ALL_BANDS) {
      assert.ok(["reassuring", "caution"].includes(bandPresentation(band).tone));
    }
  });

  it("never produces a fake/genuine verdict word, and only ever negates 'counterfeit'", () => {
    for (const band of ALL_BANDS) {
      const p = bandPresentation(band);
      const blob = `${p.headline} ${p.summary}`.toLowerCase();
      assert.doesNotMatch(blob, /\bfake\b/);
      assert.doesNotMatch(blob, /\bgenuine\b/);
      // 'counterfeit' is permitted only in the negating "no counterfeit indicators" headline,
      // never as a positive accusation ("this is a counterfeit").
      const withoutNegation = blob.replace(/no counterfeit indicators/g, "");
      assert.doesNotMatch(withoutNegation, /\bcounterfeit\b/);
    }
  });
});

describe("evidenceQuality — read clarity, kept separate from the verdict", () => {
  it("buckets a clear read above 80%", () => {
    assert.equal(evidenceQuality(0.91).label, "Clear");
    assert.equal(evidenceQuality(0.91).percent, 91);
  });

  it("buckets a partial read in the middle and a limited read low", () => {
    assert.equal(evidenceQuality(0.6).label, "Partial");
    assert.equal(evidenceQuality(0.3).label, "Limited");
  });

  it("frames the line as how clearly the card was *read*, never as verdict-certainty", () => {
    const line = evidenceQualityLine(evidenceQuality(0.83)).toLowerCase();
    assert.match(line, /read the card/);
    // It must never claim a probability about the verdict itself.
    assert.doesNotMatch(line, /risk|authentic|fake|genuine|sure/);
  });

  it("clamps an out-of-range confidence rather than over/under-reporting", () => {
    assert.equal(evidenceQuality(1.4).percent, 100);
    assert.equal(evidenceQuality(-0.2).percent, 0);
  });
});

describe("signalRead — deviation is a caution, unreadable is neutral (not a strike)", () => {
  it("reads a consistent signal as the consistent tone", () => {
    assert.equal(signalRead(signal({ observation: "consistent" })).tone, "consistent");
  });

  it("reads a deviation as caution and never the word 'fake'", () => {
    const read = signalRead(signal({ observation: "deviation" }));
    assert.equal(read.tone, "caution");
    assert.doesNotMatch(read.state.toLowerCase(), /fake|counterfeit/);
  });

  it("reads an unreadable signal as its own neutral state, not a caution", () => {
    assert.equal(signalRead(signal({ observation: "unreadable" })).tone, "unread");
  });
});

describe("accessibility — band, recommendation, and evidence quality, separately", () => {
  it("announces the band and the recommendation, then the evidence quality as a separate clause", () => {
    const said = verdictA11y(assessment({ band: "elevatedRisk", confidence: 0.83 }));
    assert.match(said, /Some signals don't match/);
    assert.match(said, /recommend professional authentication/i);
    // The evidence quality is introduced as separate, framed as read clarity.
    assert.match(said, /Evidence quality, separately/);
    assert.match(said, /clarity/);
  });

  it("never announces a fake/genuine verdict, and only ever negates 'counterfeit'", () => {
    for (const band of ALL_BANDS) {
      const said = verdictA11y(assessment({ band })).toLowerCase();
      assert.doesNotMatch(said, /\bfake\b/);
      assert.doesNotMatch(said, /\bgenuine\b/);
      const withoutNegation = said.replace(/no counterfeit indicators/g, "");
      assert.doesNotMatch(withoutNegation, /\bcounterfeit\b/);
    }
  });

  it("reads each signal with its name, state, and the human detail", () => {
    const said = signalA11y(signal({ kind: "holo_signature", observation: "deviation", detail: "Foil falls off differently." }));
    assert.match(said, /Holo \/ foil: doesn't match\. Foil falls off differently\./);
  });
});
