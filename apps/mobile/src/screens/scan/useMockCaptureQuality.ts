import { useCallback, useEffect, useRef, useState } from "react";

import type { ChipState } from "@/components";

// Stand-in for the real capture↔ML signal stream (master plan §7). The live app
// will feed focus/glare/framing from the on-device detector; here a scripted
// sequence walks the three chips from "working" to "pass" so the lock choreography
// is demonstrable without a camera. Replaced wholesale in P1.4 — its shape (a
// {signal -> state} snapshot + a derived `locked`) is the real contract.

export type QualitySignals = {
  focus: ChipState;
  glare: ChipState;
  frame: ChipState;
};

export type CaptureQuality = {
  signals: QualitySignals;
  /** Lock = every signal passes. The screen mirrors this to the frame + shutter. */
  locked: boolean;
  /** The first not-yet-passing signal, for the refuse-to-grade coaching line. */
  firstFailing: keyof QualitySignals | null;
  /** Manual override for the demo controls (and future "tap to refocus"). */
  cycle: () => void;
};

const SEQUENCE: QualitySignals[] = [
  { focus: "working", glare: "working", frame: "working" },
  { focus: "working", glare: "working", frame: "pass" },
  { focus: "pass", glare: "working", frame: "pass" },
  { focus: "pass", glare: "pass", frame: "pass" },
];

export function useMockCaptureQuality(autoplay = true): CaptureQuality {
  const [step, setStep] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!autoplay) return;
    // Walk toward lock, then hold — mimics a user steadying the card into place.
    timer.current = setInterval(() => {
      setStep((s) => (s < SEQUENCE.length - 1 ? s + 1 : s));
    }, 1400);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [autoplay]);

  const cycle = useCallback(() => {
    setStep((s) => (s + 1) % SEQUENCE.length);
  }, []);

  const signals = SEQUENCE[step] ?? SEQUENCE[0]!;
  const order: (keyof QualitySignals)[] = ["focus", "glare", "frame"];
  const firstFailing = order.find((k) => signals[k] !== "pass") ?? null;
  const locked = firstFailing === null;

  return { signals, locked, firstFailing, cycle };
}
