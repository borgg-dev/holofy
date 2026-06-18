import { useCallback, useEffect, useRef, useState } from "react";

import { CAPTURE_PLAN, type CaptureSignals } from "./capturePlan";

// Stand-in for the real per-angle capture↔ML signal stream (master plan §7), the
// counterpart to the scan-frame's useMockCaptureQuality. On device, focus/skew/glare
// come from the on-device detector; here a scripted sequence walks each angle from
// "working" toward "pass" so the lock + advance choreography is demonstrable without a
// camera. The shape it returns — a {signal -> state} snapshot, a derived `locked`, and
// the angle cursor — is the real contract the live detector slots into.

export type GuidedCaptureState = {
  /** Index into CAPTURE_PLAN of the angle being captured. */
  angleIndex: number;
  signals: CaptureSignals;
  /** Lock = every signal for the current angle passes. */
  locked: boolean;
  /** First not-yet-passing signal, for the refuse-to-grade coaching line. */
  firstFailing: keyof CaptureSignals | null;
  /** Captured count (advances on each accepted angle). */
  capturedCount: number;
  total: number;
  /** True once every angle has been captured — the screen hands off to the gauge. */
  complete: boolean;
  /** Accept the current angle (only meaningful when locked) and advance. */
  capture: () => void;
};

// Each angle walks this short sequence toward a clean lock, mimicking a user steadying
// and squaring the card. The detail (skew passing last) is the realistic order — getting
// square-on is the slowest part.
const SEQUENCE: CaptureSignals[] = [
  { focus: "working", skew: "working", glare: "working" },
  { focus: "pass", skew: "working", glare: "working" },
  { focus: "pass", skew: "working", glare: "pass" },
  { focus: "pass", skew: "pass", glare: "pass" },
];

const SIGNAL_ORDER: (keyof CaptureSignals)[] = ["focus", "skew", "glare"];

export function useGuidedCapture(autoplay = true): GuidedCaptureState {
  const [angleIndex, setAngleIndex] = useState(0);
  const [step, setStep] = useState(0);
  const [capturedCount, setCapturedCount] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const total = CAPTURE_PLAN.length;
  const complete = capturedCount >= total;

  // Walk the current angle toward lock, then hold; re-arms from the start on each new angle.
  useEffect(() => {
    if (!autoplay || complete) return;
    timer.current = setInterval(() => {
      setStep((s) => (s < SEQUENCE.length - 1 ? s + 1 : s));
    }, 1100);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [autoplay, complete, angleIndex]);

  const signals = SEQUENCE[step] ?? SEQUENCE[0]!;
  const firstFailing = SIGNAL_ORDER.find((k) => signals[k] !== "pass") ?? null;
  const locked = firstFailing === null;

  const capture = useCallback(() => {
    if (!locked || complete) return;
    setCapturedCount((n) => n + 1);
    setAngleIndex((i) => Math.min(i + 1, total - 1));
    setStep(0);
  }, [locked, complete, total]);

  return {
    angleIndex,
    signals,
    locked,
    firstFailing,
    capturedCount,
    total,
    complete,
    capture,
  };
}
