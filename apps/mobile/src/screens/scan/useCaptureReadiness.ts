import type { ChipState } from "@/components";

// Capture readiness — honest interim.
//
// The design's lock choreography is meant to be driven by a real on-device focus/glare/framing
// detector (master plan §7). We don't have that on-device signal yet, and a *scripted* one that
// pretends to measure — refusing the shutter for a few seconds, then claiming "Sharp / No glare"
// regardless of the actual frame — is dishonest and blocks good captures. Until the real
// detector lands, capture is always available and the chips are steady framing *guidance*, not a
// measured pass: the backend recognizer is the real quality judge and returns honest
// retake/confirm guidance from the actual photo.

export type QualitySignals = {
  focus: ChipState;
  glare: ChipState;
  frame: ChipState;
};

export type CaptureQuality = {
  signals: QualitySignals;
  /** Capture is always allowed — we never refuse a shot on an unmeasured signal. */
  locked: boolean;
  /** No fake "first failing" signal while there's nothing real to fail on. */
  firstFailing: keyof QualitySignals | null;
};

// Steady guidance state. "working" reads as a calm amber reminder (never a green "verified
// pass" we can't back up, never a red alarm).
const GUIDANCE: QualitySignals = { focus: "working", glare: "working", frame: "working" };

export function useCaptureReadiness(): CaptureQuality {
  return { signals: GUIDANCE, locked: true, firstFailing: null };
}
