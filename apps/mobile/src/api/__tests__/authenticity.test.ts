import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createFixtureClient } from "../client";
import {
  AUTHENTICITY_ELEVATED,
  AUTHENTICITY_INCONCLUSIVE,
  AUTHENTICITY_NOT_ASSESSED,
  AUTHENTICITY_RETAKE,
  AUTHENTICITY_STRONG,
} from "../fixtures";
import { MappingError, mapAuthenticity } from "../mapping";
import type { WireAuthenticityResponse } from "../types";

describe("mapAuthenticity — assessed", () => {
  it("maps the band (snake→camel), the signals, the evidence-quality confidence, and the disclaimer", () => {
    const r = mapAuthenticity(AUTHENTICITY_STRONG);
    assert.equal(r.status, "assessed");
    if (r.status !== "assessed") return;
    assert.equal(r.band, "strongSignals");
    assert.equal(r.signals.length, 5);
    assert.equal(r.confidence, 0.91);
    assert.equal(r.recommendAuthentication, true);
    assert.equal(r.referenceValueEur, 289.0);
    assert.ok(r.disclaimer.includes("not a verdict"));
  });

  it("maps the most-adverse band as elevatedRisk, never a fake/genuine field", () => {
    const r = mapAuthenticity(AUTHENTICITY_ELEVATED);
    if (r.status !== "assessed") return;
    assert.equal(r.band, "elevatedRisk");
    // Guard against a regression smuggling in a boolean verdict.
    const asRecord = r as unknown as Record<string, unknown>;
    assert.equal(asRecord.isFake, undefined);
    assert.equal(asRecord.isGenuine, undefined);
    assert.equal(asRecord.fake, undefined);
  });

  it("maps the inconclusive band, preserving an unreadable signal as its own observation", () => {
    const r = mapAuthenticity(AUTHENTICITY_INCONCLUSIVE);
    if (r.status !== "assessed") return;
    assert.equal(r.band, "inconclusive");
    const holo = r.signals.find((s) => s.kind === "holo_signature");
    assert.equal(holo?.observation, "unreadable");
  });

  it("keeps each signal's read-confidence as a per-signal number (not the composite)", () => {
    const r = mapAuthenticity(AUTHENTICITY_STRONG);
    if (r.status !== "assessed") return;
    const print = r.signals.find((s) => s.kind === "print_pattern");
    assert.equal(print?.confidence, 0.94);
    // The composite confidence is distinct from any single signal's confidence.
    assert.notEqual(r.confidence, print?.confidence);
  });

  it("throws if an assessed payload carries no signals", () => {
    const broken: WireAuthenticityResponse = {
      ...AUTHENTICITY_STRONG,
      assessment: { ...AUTHENTICITY_STRONG.assessment!, signals: [] },
    };
    assert.throws(() => mapAuthenticity(broken), MappingError);
  });

  it("throws if an assessed status is missing its assessment payload", () => {
    const broken: WireAuthenticityResponse = { ...AUTHENTICITY_STRONG, assessment: null };
    assert.throws(() => mapAuthenticity(broken), MappingError);
  });
});

describe("mapAuthenticity — retake and not_assessed", () => {
  it("maps a poor capture to a retake with coaching reasons", () => {
    const r = mapAuthenticity(AUTHENTICITY_RETAKE);
    assert.equal(r.status, "retake");
    if (r.status !== "retake") return;
    assert.equal(r.reasons.length, 2);
    assert.ok(r.reasons.some((reason) => /holo/i.test(reason)));
  });

  it("maps a below-threshold card to notAssessed (not a fake score)", () => {
    const r = mapAuthenticity(AUTHENTICITY_NOT_ASSESSED);
    assert.equal(r.status, "notAssessed");
    if (r.status !== "notAssessed") return;
    assert.ok(r.reasons.length >= 1);
    assert.ok(r.reasons.some((reason) => /value/i.test(reason)));
  });

  it("throws when a refuse-path carries no reasons to explain it", () => {
    const broken: WireAuthenticityResponse = { ...AUTHENTICITY_RETAKE, reasons: [] };
    assert.throws(() => mapAuthenticity(broken), MappingError);
  });
});

describe("fixture client — authenticity path", () => {
  it("returns each outcome for its keyed capture ref", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const strong = await client.authenticity({ captureRef: "mock-auth-strong", cardId: "origins-8" });
    assert.equal(strong.status, "assessed");
    if (strong.status === "assessed") assert.equal(strong.band, "strongSignals");

    const elevated = await client.authenticity({ captureRef: "mock-auth-elevated", cardId: "origins-12" });
    if (elevated.status === "assessed") assert.equal(elevated.band, "elevatedRisk");

    const retake = await client.authenticity({ captureRef: "mock-auth-retake", cardId: "origins-12" });
    assert.equal(retake.status, "retake");

    const notAssessed = await client.authenticity({
      captureRef: "mock-auth-not-assessed",
      cardId: "echo-12",
    });
    assert.equal(notAssessed.status, "notAssessed");
  });
});

// The structural guarantee (charter §3.5): no fixture, in any state, ever serializes a
// boolean fake/genuine verdict or an accusatory string. This is the wire-level half of the
// guard; band.test.ts covers the same for the presentation layer.
describe("no fake/genuine verdict anywhere on the wire", () => {
  const ALL: WireAuthenticityResponse[] = [
    AUTHENTICITY_STRONG,
    AUTHENTICITY_INCONCLUSIVE,
    AUTHENTICITY_ELEVATED,
    AUTHENTICITY_RETAKE,
    AUTHENTICITY_NOT_ASSESSED,
  ];

  it("never emits a fake/genuine/counterfeit verdict word outside the self-negating disclaimer", () => {
    for (const wire of ALL) {
      // The disclaimer legitimately *negates* both words ("not a determination that a card
      // is genuine or counterfeit"); strip it, then nothing else may use them at all.
      const blob = JSON.stringify(wire).toLowerCase().replace(wire.disclaimer.toLowerCase(), "");
      assert.doesNotMatch(blob, /\bfake\b/, "no 'fake' verdict");
      assert.doesNotMatch(blob, /\bgenuine\b/, "no 'genuine' verdict");
      assert.doesNotMatch(blob, /\bcounterfeit\b/, "no 'counterfeit' claim outside the disclaimer");
    }
  });

  it("never carries a boolean verdict key", () => {
    for (const wire of ALL) {
      const a = wire.assessment;
      if (!a) continue;
      const asRecord = a as unknown as Record<string, unknown>;
      assert.equal(asRecord.is_fake, undefined);
      assert.equal(asRecord.is_genuine, undefined);
      assert.equal(asRecord.authentic, undefined);
    }
  });
});
