import type { ChipState } from "@/components";
import type { QualitySignals } from "./useMockCaptureQuality";

// All scan-frame microcopy in one place — the strings are product copy, not
// placeholders, and the file is the seam where localization (FR→ES→IT→DE→EN)
// will swap them. Chips never say "error": amber is a coaching state.

type SignalCopy = Record<ChipState, string>;

const CHIP_COPY: Record<keyof QualitySignals, { signal: string; states: SignalCopy }> = {
  focus: {
    signal: "Focus",
    states: { pass: "Sharp", working: "Focusing…", fail: "Too blurry" },
  },
  glare: {
    signal: "Glare",
    states: { pass: "No glare", working: "Tilt from light", fail: "Glare on holo" },
  },
  frame: {
    signal: "Frame",
    states: { pass: "All 4 corners", working: "Show full card", fail: "Corner cut off" },
  },
};

export function chipFor(key: keyof QualitySignals, state: ChipState) {
  const c = CHIP_COPY[key];
  return { signal: c.signal, label: c.states[state] };
}

// The refuse-to-grade line names the specific thing to fix and never blames the user.
const REFUSE_REASON: Record<keyof QualitySignals, string> = {
  focus: "hold steady so it sharpens",
  glare: "tilt away from the light",
  frame: "fit all four corners in",
};

export function refuseMessage(reason: keyof QualitySignals | null): string {
  const tail = reason ? REFUSE_REASON[reason] : "let's line the card up";
  return `Let's get a cleaner shot — ${tail}.`;
}

export const SHUTTER_REST = "Hold steady";
export const SHUTTER_LOCKED = "Capture";

export const LOCK_ANNOUNCE = "Card locked — ready to capture";
export const EMPTY_HINT = "Lay the card on a flat, dark surface";
