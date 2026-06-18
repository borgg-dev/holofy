import { useCallback, useEffect, useRef, useState } from "react";

import { AUTHENTICITY_PLAN, type CaptureSignals } from "./capturePlan";

// Stand-in for the real per-shot capture↔ML signal stream (master plan §7), the authenticity
// counterpart to pre-grade's useGuidedCapture. Same contract — a {signal -> state} snapshot,
// a derived `locked`, and the shot cursor — so the live detector slots in unchanged; only the
// plan it walks differs (a macro print close-up + two holo tilts). On device focus/skew/glare
// come from the on-device detector; here a scripted sequence walks each shot toward a lock so
// the choreography is demonstrable without a camera.

export type GuidedCaptureState = {
  /** Index into AUTHENTICITY_PLAN of the shot being captured. */
  shotIndex: number;
  signals: CaptureSignals;
  /** Lock = every signal for the current shot passes. */
  locked: boolean;
  /** First not-yet-passing signal, for the refuse-to-screen coaching line. */
  firstFailing: keyof CaptureSignals | null;
  /** Captured count (advances on each accepted shot). */
  capturedCount: number;
  total: number;
  /** True once every shot has been captured — the screen hands off to screening. */
  complete: boolean;
  /** Accept the current shot (only meaningful when locked) and advance. */
  capture: () => void;
};

// Each shot walks this short sequence toward a clean lock, mimicking a user steadying and
// framing the card. Focus passes early (the macro close-up), glare last (tilting the foil
// out of a hotspot is the slow part) — the realistic order for an authenticity capture.
const SEQUENCE: CaptureSignals[] = [
  { focus: "working", skew: "working", glare: "working" },
  { focus: "pass", skew: "working", glare: "working" },
  { focus: "pass", skew: "pass", glare: "working" },
  { focus: "pass", skew: "pass", glare: "pass" },
];

const SIGNAL_ORDER: (keyof CaptureSignals)[] = ["focus", "skew", "glare"];

export function useGuidedCapture(autoplay = true): GuidedCaptureState {
  const [shotIndex, setShotIndex] = useState(0);
  const [step, setStep] = useState(0);
  const [capturedCount, setCapturedCount] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const total = AUTHENTICITY_PLAN.length;
  const complete = capturedCount >= total;

  // Walk the current shot toward lock, then hold; re-arms from the start on each new shot.
  useEffect(() => {
    if (!autoplay || complete) return;
    timer.current = setInterval(() => {
      setStep((s) => (s < SEQUENCE.length - 1 ? s + 1 : s));
    }, 1100);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [autoplay, complete, shotIndex]);

  const signals = SEQUENCE[step] ?? SEQUENCE[0]!;
  const firstFailing = SIGNAL_ORDER.find((k) => signals[k] !== "pass") ?? null;
  const locked = firstFailing === null;

  const capture = useCallback(() => {
    if (!locked || complete) return;
    setCapturedCount((n) => n + 1);
    setShotIndex((i) => Math.min(i + 1, total - 1));
    setStep(0);
  }, [locked, complete, total]);

  return {
    shotIndex,
    signals,
    locked,
    firstFailing,
    capturedCount,
    total,
    complete,
    capture,
  };
}
