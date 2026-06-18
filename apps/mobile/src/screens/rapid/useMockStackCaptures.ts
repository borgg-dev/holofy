import { useCallback, useRef, useState } from "react";

import type { CardIdentity, PriceQuote } from "@/api";
import type { CaptureRead } from "./stack";

// Stand-in for the rapid-mode capture↔ML stream (master plan §7). On device each flip is
// a real detection the on-device recognizer reads; here a scripted flip sequence feeds the
// live filmstrip so the merge animation, the running total, and the confirm-at-end handoff
// are demonstrable without a camera. The sequence is built to mirror what the batch fixture
// confirms — the same Tidecaller flipped twice (the dedupe), a Grovekeeper, an Emberwyrm
// that reads pending (the batch asks to confirm it), and a glared miss — so the live preview
// and the authoritative review tell one consistent story. Replaced wholesale when the real
// camera lands; its shape (a {captureRef, read} per flip) is the real contract.

const identity = (
  canonicalId: string,
  name: string,
  setName: string,
  collectorNumber: string,
  variant: CardIdentity["variant"]
): CardIdentity => ({ canonicalId, name, setName, collectorNumber, language: "en", variant });

const price = (canonicalId: string, value: number, avg30: number): PriceQuote => ({
  canonicalId,
  currency: "EUR",
  value,
  basis: "trend",
  low: null,
  avg30,
  source: "cardmarket",
  asOf: new Date("2026-06-18T00:00:00Z"),
  ageHours: 6,
  listingUrl: null,
});

const TIDECALLER = identity("origins-8", "Tidecaller Leviath", "Origins Vault", "8/120", "holo");
const GROVEKEEPER = identity("wild-15", "Grovekeeper Thornmaw", "Wildgrowth", "15/88", "holo");

// Flip order, matched to STACK_BATCH in api/fixtures so the live read and the confirmed
// review never contradict each other. The fourth flip is the same Tidecaller as the first
// (the dedupe-merge); the Emberwyrm reads `pending` because the batch returns it as a
// needs_confirmation; the seventh is the glared miss the review offers to re-capture.
const FLIPS: { captureRef: string; read: CaptureRead }[] = [
  { captureRef: "stack-cap-1", read: { kind: "identified", identity: TIDECALLER, price: price("origins-8", 289, 271.4) } },
  { captureRef: "stack-cap-2", read: { kind: "identified", identity: GROVEKEEPER, price: price("wild-15", 61.4, 58.9) } },
  { captureRef: "stack-cap-3", read: { kind: "pending" } },
  { captureRef: "stack-cap-4", read: { kind: "identified", identity: TIDECALLER, price: price("origins-8", 289, 271.4) } },
  { captureRef: "stack-cap-7", read: { kind: "unreadable" } },
];

export type StackCaptureSource = {
  /** Pull the next scripted flip, or null once the demo stack is exhausted. */
  next: () => { captureRef: string; read: CaptureRead } | null;
  /** Flips remaining in the scripted stack — drives the "more to flip" affordance. */
  remaining: number;
  done: boolean;
};

export function useMockStackCaptures(): StackCaptureSource {
  const cursor = useRef(0);
  const [remaining, setRemaining] = useState(FLIPS.length);

  const next = useCallback(() => {
    const flip = FLIPS[cursor.current];
    if (!flip) return null;
    cursor.current += 1;
    setRemaining(FLIPS.length - cursor.current);
    return flip;
  }, []);

  return { next, remaining, done: remaining === 0 };
}
