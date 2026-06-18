// The consent UI's view-logic, kept pure so it's unit-tested without a renderer — the same
// split as the authenticity verdict's `band.ts`. Three trust rules from charter §3.5 live
// here, in code rather than prose, so they can't drift between the screen and the prompt:
//   1. Default off. Consent is never pre-granted; the toggle and the prompt both start from
//      "off", and the affirmative action is the explicit opt-in. `CONSENT_DEFAULT` is the one
//      source of that default, so a regression flips a test, not just a pixel.
//   2. The toggle's spoken state matches its value. The screen reader hears "on"/"off" exactly
//      as the switch is set — `consentToggleA11y` derives the label from the value, never the
//      other way round, so the a11y state can't contradict the visual one.
//   3. Decline carries equal weight. The first-capture prompt's two choices render at the same
//      visual tier — no pre-selected "yes", no steering fill (a dark pattern). `promptActions`
//      hands both buttons the same tier, so "equal weight" is asserted, not assumed.

import { firstCapturePrompt, privacyCopy } from "./copy";

/** Consent is off until the collector chooses it (charter §3.5 / GDPR). The one default. */
export const CONSENT_DEFAULT = false;

/**
 * The toggle's spoken label and checked state for a given value. The label is derived from the
 * value so the reader's state always matches the switch's — they can never disagree.
 */
export function consentToggleA11y(granted: boolean): { label: string; checked: boolean } {
  return {
    label: granted ? privacyCopy.toggleA11yOn : privacyCopy.toggleA11yOff,
    checked: granted,
  };
}

/** The control tier each button in the first-capture prompt renders at. */
export type PromptAction = { label: string; tier: "secondary"; accessibilityHint: string };

/**
 * The accept / decline actions for the first-capture prompt. Both at the same `secondary`
 * tier — equal visual weight, so nothing steers the eye toward opting in (no dark pattern).
 */
export function promptActions(): { accept: PromptAction; decline: PromptAction } {
  return {
    accept: {
      label: firstCapturePrompt.accept,
      tier: "secondary",
      accessibilityHint: firstCapturePrompt.acceptA11y,
    },
    decline: {
      label: firstCapturePrompt.decline,
      tier: "secondary",
      accessibilityHint: firstCapturePrompt.declineA11y,
    },
  };
}
