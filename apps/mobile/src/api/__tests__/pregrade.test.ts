import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createFixtureClient } from "../client";
import { PREGRADE_ESTIMATED, PREGRADE_RETAKE } from "../fixtures";
import { LIMITED_CONFIDENCE, MappingError, axisProvenance, mapPregrade } from "../mapping";
import type { WirePregradeResponse } from "../types";

describe("mapPregrade — estimated", () => {
  it("maps the band, sub-scores, confidence, and disclaimer", () => {
    const r = mapPregrade(PREGRADE_ESTIMATED);
    assert.equal(r.status, "estimated");
    if (r.status !== "estimated") return;
    assert.deepEqual(r.range, { likelyLow: 8, likelyHigh: 9, atLeast: 9, pAtLeast: 0.62 });
    assert.equal(r.subScores.length, 4);
    assert.equal(r.confidence, 0.78);
    assert.ok(r.disclaimer.includes("not an official grade"));
  });

  it("never carries a single absolute grade field", () => {
    const r = mapPregrade(PREGRADE_ESTIMATED);
    if (r.status !== "estimated") return;
    // The honest contract: the headline is a band, not a number. Guard against a
    // regression that smuggles one in.
    assert.equal((r.range as Record<string, unknown>).grade, undefined);
    assert.ok(r.range.likelyLow <= r.range.likelyHigh);
  });

  it("tags centering measured, other axes estimated, and a low-confidence axis limited", () => {
    const r = mapPregrade(PREGRADE_ESTIMATED);
    if (r.status !== "estimated") return;
    const byAxis = Object.fromEntries(r.subScores.map((s) => [s.axis, s.provenance]));
    assert.equal(byAxis.centering, "measured");
    assert.equal(byAxis.corners, "estimated");
    assert.equal(byAxis.edges, "estimated");
    // Surface is confident 0.42 < threshold → limited, the surface-blind case.
    assert.equal(byAxis.surface, "limited");
  });

  it("throws if an estimated payload is missing its probability range", () => {
    const broken: WirePregradeResponse = { ...PREGRADE_ESTIMATED, probability: null };
    assert.throws(() => mapPregrade(broken), MappingError);
  });
});

describe("axisProvenance", () => {
  it("marks any axis below the confidence threshold as limited", () => {
    assert.equal(axisProvenance("corners", LIMITED_CONFIDENCE - 0.01), "limited");
    assert.equal(axisProvenance("centering", LIMITED_CONFIDENCE - 0.01), "limited");
  });
  it("keeps centering measured and the bought axes estimated when confident", () => {
    assert.equal(axisProvenance("centering", 0.9), "measured");
    assert.equal(axisProvenance("surface", 0.9), "estimated");
  });
});

describe("mapPregrade — retake", () => {
  it("maps the coaching reasons and disclaimer", () => {
    const r = mapPregrade(PREGRADE_RETAKE);
    assert.equal(r.status, "retake");
    if (r.status !== "retake") return;
    assert.equal(r.reasons.length, 2);
    assert.ok(r.reasons[0]!.toLowerCase().includes("tilt"));
  });

  it("throws when a retake carries no reasons to coach on", () => {
    const broken: WirePregradeResponse = { ...PREGRADE_RETAKE, reasons: [] };
    assert.throws(() => mapPregrade(broken), MappingError);
  });
});

describe("fixture client — pregrade path", () => {
  it("estimates a clean capture ref", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const r = await client.pregrade({ captureRef: "mock-capture-clean" });
    assert.equal(r.status, "estimated");
  });

  it("returns a retake for a sub-threshold capture ref", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const r = await client.pregrade({ captureRef: "mock-capture-retake" });
    assert.equal(r.status, "retake");
    if (r.status !== "retake") return;
    assert.ok(r.reasons.length >= 1);
  });
});
