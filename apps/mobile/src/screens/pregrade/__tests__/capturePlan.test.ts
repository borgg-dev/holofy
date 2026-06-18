import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CAPTURE_PLAN,
  chipOrderFor,
  refuseMessage,
  type CaptureAngle,
} from "../capturePlan";

describe("capture plan — the multi-angle dependency", () => {
  it("includes a square-on pass and two raking surface passes", () => {
    const ids = CAPTURE_PLAN.map((a) => a.id);
    assert.ok(ids.includes("front-flat"), "needs a flat front for the geometric axes");
    const surface = CAPTURE_PLAN.filter((a) => a.id.startsWith("surface-rake"));
    assert.equal(surface.length, 2, "surface needs two opposite raking angles");
  });

  it("makes skew the primary signal on the flat passes (the dominant failure)", () => {
    const front = CAPTURE_PLAN.find((a) => a.id === "front-flat")!;
    assert.equal(front.primary, "skew");
  });

  it("makes glare the primary signal on the surface passes (glare hides the holo)", () => {
    const rake = CAPTURE_PLAN.find((a) => a.id === "surface-rake-left")!;
    assert.equal(rake.primary, "glare");
  });
});

describe("chipOrderFor — primary signal leads", () => {
  const angle: CaptureAngle = {
    id: "x",
    label: "X",
    instruction: "i",
    primary: "glare",
  };
  it("surfaces the angle's primary signal first, keeps all three", () => {
    const order = chipOrderFor(angle);
    assert.equal(order[0], "glare");
    assert.deepEqual([...order].sort(), ["focus", "glare", "skew"]);
  });
});

describe("refuseMessage — coaching, never blame", () => {
  it("names the specific fix for the failing signal", () => {
    assert.match(refuseMessage("skew"), /level the card/);
    assert.match(refuseMessage("glare"), /tilt away from the light/);
  });
  it("falls back to a calm line when nothing specific is failing", () => {
    assert.match(refuseMessage(null), /line the card up/);
  });
  it("always frames it as a cleaner shot, not a failure", () => {
    for (const k of ["focus", "skew", "glare", null] as const) {
      assert.match(refuseMessage(k), /cleaner shot/);
    }
  });
});
