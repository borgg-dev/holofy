import { useEffect, useRef, useState } from "react";

import { countUpValue } from "@/api";
import { useReduceMotion, useTheme } from "@/theme";
import { ValueText } from "./ValueText";

type Props = {
  /** Final amount in major units (euros). */
  amount: number;
  currency?: string;
  locale?: string;
  variant?: "displayXl" | "displayLg" | "displayMd" | "titleLg";
  tone?: "primary" | "reward" | "secondary";
  /** Override the count-up duration; defaults to the token countUp duration. */
  durationMs?: number;
};

// The reveal value (foil-reveal.md): an odometer-style count from 0 → amount on mount,
// easing out so it sprints then settles. Reduced motion shows the final figure instantly.
// Screen-reader users always get the settled value at once via ValueText's label — the
// animation never gates the real number.
export function CountUpValue({
  amount,
  currency = "EUR",
  locale = "de-DE",
  variant = "displayXl",
  tone = "primary",
  durationMs,
}: Props) {
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const duration = durationMs ?? theme.motion.duration.countUp;

  const [display, setDisplay] = useState(reduceMotion ? amount : 0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(amount);
      return;
    }
    const start = Date.now();
    let active = true;
    const tick = () => {
      if (!active) return;
      const elapsed = Date.now() - start;
      setDisplay(countUpValue(amount, elapsed, duration));
      if (elapsed < duration) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      active = false;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [amount, duration, reduceMotion]);

  // ValueText carries the settled figure as its own SR label; a screen that needs a
  // richer announcement ("…up 4.2 percent") renders it on a sibling polite live region.
  return (
    <ValueText
      amount={display}
      currency={currency}
      locale={locale}
      variant={variant}
      tone={tone}
    />
  );
}
