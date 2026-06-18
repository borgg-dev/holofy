// Count-up math for the reveal value (foil-reveal.md: "count-up 0 → final, odometer
// roll"). Kept as a pure function of elapsed time so the easing and clamping are tested
// without a clock; the hook in `useCountUp` just feeds it `Date.now()` deltas.

/**
 * Value to display at `elapsedMs` into a count from 0 → `target` over `durationMs`.
 * Uses an ease-out so it sprints then settles — the odometer feel — and is exact at the
 * endpoints (0 at t≤0, `target` at t≥duration) so the final figure is never approximate.
 */
export function countUpValue(target: number, elapsedMs: number, durationMs: number): number {
  if (durationMs <= 0 || elapsedMs >= durationMs) return target;
  if (elapsedMs <= 0) return 0;
  const t = elapsedMs / durationMs;
  return target * easeOutCubic(t);
}

function easeOutCubic(t: number): number {
  const inv = 1 - t;
  return 1 - inv * inv * inv;
}
