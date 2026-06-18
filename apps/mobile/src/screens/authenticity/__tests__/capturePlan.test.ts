import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  AUTHENTICITY_PLAN,
  chipOrderFor,
  refuseMessage,
  type AuthenticityShot,
} from "../capturePlan";

describe("authenticity capture plan — print + holo, the anti-counterfeit signals", () => {
  it("includes a macro print close-up and two holo-tilt passes", () => {
    const ids = AUTHENTICITY_PLAN.map((s) => s.id);
    assert.ok(ids.includes("print-macro"), "needs a macro close-up for the print pattern");
    const holo = AUTHENTICITY_PLAN.filter((s) => s.id.startsWith("holo-tilt"));
    assert.equal(holo.length, 2, "the holo signature needs two opposite tilt angles");
  });

  it("makes focus the primary signal on the print close-up (sharpness reads the dot pattern)", () => {
    const macro = AUTHENTICITY_PLAN.find((s) => s.id === "print-macro")!;
    assert.equal(macro.primary, "focus");
  });

  it("makes glare the primary signal on the holo passes (glare hides the foil signature)", () => {
    const tilt = AUTHENTICITY_PLAN.find((s) => s.id === "holo-tilt-left")!;
    assert.equal(tilt.primary, "glare");
  });
});

describe("chipOrderFor — the shot's primary signal leads", () => {
  const shot: AuthenticityShot = { id: "x", label: "X", instruction: "i", primary: "glare" };
  it("surfaces the primary signal first, keeps all three", () => {
    const order = chipOrderFor(shot);
    assert.equal(order[0], "glare");
    assert.deepEqual([...order].sort(), ["focus", "glare", "skew"]);
  });
});

describe("refuseMessage — coaching, never blame", () => {
  it("names the specific fix for the failing signal", () => {
    assert.match(refuseMessage("focus"), /move in until the print sharpens/);
    assert.match(refuseMessage("glare"), /tilt the foil away from the light/);
  });
  it("always frames it as a cleaner shot, never a failure or an accusation", () => {
    for (const k of ["focus", "skew", "glare", null] as const) {
      assert.match(refuseMessage(k), /cleaner shot/);
    }
  });
});
