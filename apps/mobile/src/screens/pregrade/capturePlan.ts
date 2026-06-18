// The multi-angle capture plan — the capture↔ML dependency made concrete.
//
// From the grading spike FINDINGS: perspective/skew is the dominant failure mode (a
// tilted card makes centering unmeasurable and warps every edge), and glare hides the
// surface defects that separate a 9 from a 10. So a trustworthy pre-grade needs more
// than one flat photo: a square-on pass for centering/corners/edges, then two raking
// passes that catch the holo's surface from opposite light angles. Each angle coaches
// the *specific* thing that ruins it — generic "hold steady" doesn't earn the estimate.
//
// This is the plan the UI walks; the per-angle quality signals (focus/skew/glare) come
// from the on-device detector on real hardware (mocked here behind the same shape).

import type { ChipState } from "@/components";

/** The live quality signals graded per angle. Skew is first-class — it's the top failure. */
export type CaptureSignals = {
  /** Sharpness. A soft frame can't resolve corner whitening or edge nicks. */
  focus: ChipState;
  /** Perspective/skew. The dominant failure: a tilted card warps centering + edges. */
  skew: ChipState;
  /** Glare. On the surface passes this is what hides holo scratches. */
  glare: ChipState;
};

export type CaptureAngle = {
  id: string;
  /** Short label shown as the step and announced on advance, e.g. "Front, square-on". */
  label: string;
  /** The instruction for this angle — names the one thing that makes it count. */
  instruction: string;
  /** Which signal this angle is most sensitive to; surfaces first in the coaching. */
  primary: keyof CaptureSignals;
};

// Four angles: a flat front for the geometric axes, then back, then two raking-light
// passes for surface. Surface needs two opposite tilts because a single angle leaves
// half the holo in specular glare — the reason the single-shot estimate is surface-blind.
export const CAPTURE_PLAN: readonly CaptureAngle[] = [
  {
    id: "front-flat",
    label: "Front, square-on",
    instruction: "Shoot straight down so all four borders stay parallel — this is what makes centering measurable.",
    primary: "skew",
  },
  {
    id: "back-flat",
    label: "Back, square-on",
    instruction: "Flip it and stay square-on. The back's centering and corners count too.",
    primary: "skew",
  },
  {
    id: "surface-rake-left",
    label: "Surface, tilt left",
    instruction: "Tilt the card so light rakes across the holo from the left — this reveals scratches a flat shot hides.",
    primary: "glare",
  },
  {
    id: "surface-rake-right",
    label: "Surface, tilt right",
    instruction: "Now rake the light from the right to read the other half of the surface.",
    primary: "glare",
  },
] as const;

/** SR-readable signal names + the live coaching label per state. Amber is "not yet". */
type SignalCopy = { signal: string; states: Record<ChipState, string> };

export const SIGNAL_COPY: Record<keyof CaptureSignals, SignalCopy> = {
  focus: {
    signal: "Focus",
    states: { pass: "Sharp", working: "Focusing…", fail: "Too soft" },
  },
  skew: {
    signal: "Alignment",
    states: { pass: "Square-on", working: "Level it out", fail: "Tilted" },
  },
  glare: {
    signal: "Glare",
    states: { pass: "Clean read", working: "Tilt from light", fail: "Glare on holo" },
  },
};

/** Order the chips so the angle's primary signal reads first. */
export function chipOrderFor(angle: CaptureAngle): (keyof CaptureSignals)[] {
  const rest = (["focus", "skew", "glare"] as (keyof CaptureSignals)[]).filter(
    (k) => k !== angle.primary
  );
  return [angle.primary, ...rest];
}

/** The refuse-to-grade line for the first not-yet-passing signal — never blames the user. */
const REFUSE_REASON: Record<keyof CaptureSignals, string> = {
  focus: "hold steady so it sharpens",
  skew: "level the card so the borders line up",
  glare: "tilt away from the light",
};

export function refuseMessage(reason: keyof CaptureSignals | null): string {
  const tail = reason ? REFUSE_REASON[reason] : "line the card up";
  return `Let's get a cleaner shot — ${tail}.`;
}
