// The authenticity capture plan — the capture↔ML dependency for anti-counterfeit.
//
// Authenticity reads different things than pre-grade. Pre-grade needs geometry (centering,
// corners, edges) and surface; authenticity needs the *print itself*: the CMYK rosette at
// magnification (fakes get the dot pattern wrong), and the holo's reflectance across tilt
// (foil is the hardest layer to counterfeit). So the plan coaches a tight macro close-up for
// the print pattern, then two holo-tilt passes that catch the foil from opposite angles —
// the same raking idea as pre-grade's surface, but here it's reading the holo *signature*,
// not scratches. Each shot coaches the specific thing that makes it readable.
//
// The live quality signals reuse pre-grade's CaptureSignals shape (focus/skew/glare) so the
// QualityChip + lock/refuse choreography is shared; on device they come from the same
// on-device detector, mocked here behind the same contract.

import type { CaptureSignals } from "../pregrade/capturePlan";

export type { CaptureSignals } from "../pregrade/capturePlan";

export type AuthenticityShot = {
  id: string;
  /** Short label shown as the step and announced on advance, e.g. "Print close-up". */
  label: string;
  /** The instruction — names the one thing that makes this shot readable. */
  instruction: string;
  /** The signal this shot is most sensitive to; surfaces first in the coaching. */
  primary: keyof CaptureSignals;
};

// Three shots: one macro close-up for the print pattern (focus is everything at
// magnification), then two holo-tilt passes (glare is the enemy — it hides the foil's
// reflectance, the signature we're reading).
export const AUTHENTICITY_PLAN: readonly AuthenticityShot[] = [
  {
    id: "print-macro",
    label: "Print close-up",
    instruction:
      "Move in close on the artwork until the print's tiny dot pattern is crisp — this is the texture fakes get wrong.",
    primary: "focus",
  },
  {
    id: "holo-tilt-left",
    label: "Holo, tilt left",
    instruction:
      "Tilt the card so the foil catches light from the left — we read how the holo shifts, not a flat reflection.",
    primary: "glare",
  },
  {
    id: "holo-tilt-right",
    label: "Holo, tilt right",
    instruction:
      "Now tilt the other way so the foil lights from the right. Two angles read the holo's full signature.",
    primary: "glare",
  },
] as const;

/** SR-readable signal names + the live coaching label per state. Amber is "not yet". */
type SignalCopy = { signal: string; states: Record<import("@/components").ChipState, string> };

// Authenticity speaks the same coaching vocabulary as pre-grade's capture, with the labels
// tuned to what each signal means here (sharpness reads the print; glare hides the holo).
export const SIGNAL_COPY: Record<keyof CaptureSignals, SignalCopy> = {
  focus: {
    signal: "Focus",
    states: { pass: "Crisp", working: "Focusing…", fail: "Too soft" },
  },
  skew: {
    signal: "Alignment",
    states: { pass: "Square-on", working: "Level it out", fail: "Tilted" },
  },
  glare: {
    signal: "Glare",
    states: { pass: "Holo reading", working: "Tilt from light", fail: "Glare on foil" },
  },
};

/** Order the chips so the shot's primary signal reads first. */
export function chipOrderFor(shot: AuthenticityShot): (keyof CaptureSignals)[] {
  const rest = (["focus", "skew", "glare"] as (keyof CaptureSignals)[]).filter(
    (k) => k !== shot.primary
  );
  return [shot.primary, ...rest];
}

/** The refuse-to-screen line for the first not-yet-passing signal — never blames the user. */
const REFUSE_REASON: Record<keyof CaptureSignals, string> = {
  focus: "move in until the print sharpens",
  skew: "level the card so it sits square-on",
  glare: "tilt the foil away from the light",
};

export function refuseMessage(reason: keyof CaptureSignals | null): string {
  const tail = reason ? REFUSE_REASON[reason] : "line the card up";
  return `Let's get a cleaner shot — ${tail}.`;
}
