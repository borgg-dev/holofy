import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { CONSENT_DEFAULT, consentToggleA11y, promptActions } from "../consent";
import { firstCapturePrompt, privacyCopy } from "../copy";

// The consent UI's trust rules (charter §3.5), asserted on the same view-logic the screen and
// the prompt render from — so a regression here is a failing test, not a silent dark pattern.

describe("consent default", () => {
  it("is off — consent is never pre-granted", () => {
    assert.equal(CONSENT_DEFAULT, false);
  });
});

describe("consentToggleA11y", () => {
  it("reads checked when on, and speaks the on label", () => {
    const a11y = consentToggleA11y(true);
    assert.equal(a11y.checked, true);
    assert.equal(a11y.label, privacyCopy.toggleA11yOn);
  });

  it("reads unchecked when off, and speaks the off label", () => {
    const a11y = consentToggleA11y(false);
    assert.equal(a11y.checked, false);
    assert.equal(a11y.label, privacyCopy.toggleA11yOff);
  });

  it("never lets the spoken state contradict the value", () => {
    // The checked flag is the value itself, and each value maps to its own label — the reader
    // can't hear "on" while the switch is off (the inverted-label bug Phase 3 caught).
    for (const granted of [true, false]) {
      const a11y = consentToggleA11y(granted);
      assert.equal(a11y.checked, granted);
    }
    assert.notEqual(consentToggleA11y(true).label, consentToggleA11y(false).label);
  });
});

describe("promptActions", () => {
  it("renders accept and decline at equal visual weight — no steering", () => {
    const { accept, decline } = promptActions();
    assert.equal(accept.tier, decline.tier);
    assert.equal(decline.tier, "secondary");
  });

  it("carries the reviewed copy and a11y hints for both choices", () => {
    const { accept, decline } = promptActions();
    assert.equal(accept.label, firstCapturePrompt.accept);
    assert.equal(accept.accessibilityHint, firstCapturePrompt.acceptA11y);
    assert.equal(decline.label, firstCapturePrompt.decline);
    assert.equal(decline.accessibilityHint, firstCapturePrompt.declineA11y);
  });
});
