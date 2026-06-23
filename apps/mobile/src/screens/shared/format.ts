// Cross-screen formatting helpers — the small, pure string/number shaping the reveal,
// confirm, and Vault screens share. Kept framework-free so it's unit-testable and never
// re-implemented per screen. All money rendering still goes through ValueText (Intl);
// these are the surrounding factual lines.

import type { CardIdentity, Condition, PriceQuote } from "@/api";

/** Human label for a wire Condition enum — never shows the raw snake_case key. */
const CONDITION_LABEL: Record<Condition, string> = {
  not_assessed: "Not assessed",
  mint: "Mint",
  near_mint: "Near mint",
  excellent: "Excellent",
  good: "Good",
  light_played: "Light played",
  played: "Played",
  poor: "Poor",
};

export function conditionLabel(condition: Condition): string {
  return CONDITION_LABEL[condition];
}

/** Display label for a variant — title-cased, the long-tail "normal" reads as "Holo"-style. */
const VARIANT_LABEL: Record<CardIdentity["variant"], string> = {
  normal: "Normal",
  holo: "Holo",
  reverse_holo: "Reverse holo",
  first_edition: "1st Edition",
  promo: "Promo",
};

export function variantLabel(variant: CardIdentity["variant"]): string {
  return VARIANT_LABEL[variant];
}

/**
 * The factual sub-line under a card name: "Origins Vault · 12/120 · EN · Holo".
 * Middot-separated, language uppercased — the collector's at-a-glance ID string.
 */
export function identitySubline(identity: CardIdentity): string {
  return [
    identity.setName,
    identity.collectorNumber,
    identity.language.toUpperCase(),
    variantLabel(identity.variant),
  ].join(" · ");
}

/** Screen-reader description of a card, spelled out (foil-reveal.md a11y). */
export function identityA11yLabel(identity: CardIdentity): string {
  return `${identity.name}, ${identity.setName}, number ${identity.collectorNumber.replace(
    "/",
    " of "
  )}, ${languageName(identity.language)}, ${variantLabel(identity.variant).toLowerCase()}`;
}

function languageName(code: string): string {
  const NAMES: Record<string, string> = {
    en: "English",
    de: "German",
    fr: "French",
    es: "Spanish",
    it: "Italian",
  };
  return NAMES[code] ?? code.toUpperCase();
}

export type Trend = {
  /** Signed fraction, e.g. 0.042 → +4.2%. */
  fraction: number;
  direction: "up" | "down" | "flat";
};

/**
 * Derive a 30-day trend from a quote: (value − avg30) / avg30. A price dip is *not* an
 * error — the screen pairs the sign with amber (never red) and the words up/down for SR.
 */
export function trendFromQuote(quote: PriceQuote | null): Trend | null {
  if (!quote || quote.value == null || quote.avg30 == null || quote.avg30 <= 0) {
    return null;
  }
  const fraction = (quote.value - quote.avg30) / quote.avg30;
  const rounded = Math.round(fraction * 1000) / 1000;
  return {
    fraction: rounded,
    direction: rounded > 0.0005 ? "up" : rounded < -0.0005 ? "down" : "flat",
  };
}

/** "+4.2%" / "−1.8%" / "0.0%" — uses a real minus glyph, sign always shown. */
export function formatTrendPercent(fraction: number, locale = "de-DE"): string {
  const pct = Math.abs(fraction) * 100;
  const body = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(pct);
  const sign = fraction > 0.0005 ? "+" : fraction < -0.0005 ? "−" : "";
  return `${sign}${body}%`;
}

/** "up 4.2 percent" — the SR fragment, never color-only. */
export function trendA11y(trend: Trend, locale = "de-DE"): string {
  const word = trend.direction === "up" ? "up" : trend.direction === "down" ? "down" : "flat at";
  const pct = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Math.abs(trend.fraction) * 100);
  return `${word} ${pct} percent over 30 days`;
}
