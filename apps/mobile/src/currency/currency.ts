// Display-currency model. IMPORTANT: every price in this app comes from Cardmarket in EUR — that
// is the single source of truth. A non-EUR display is a straight FX *conversion* of that EUR
// figure (today's ECB rate), NOT a native market quote: the US (TCGplayer) market can price the
// same card very differently. So the UI always labels a non-EUR amount as converted, and EUR
// stays the canonical value the server stores and totals. Keeping this layer framework-free makes
// the conversion/format logic unit-testable without React.

export type DisplayCurrency = "EUR" | "USD";

export const DISPLAY_CURRENCIES: readonly DisplayCurrency[] = ["EUR", "USD"] as const;

// AsyncStorage keys, namespaced like the theme prefs so they never collide.
export const CURRENCY_STORAGE_KEY = "holofy.display.currency";
export const RATE_CACHE_STORAGE_KEY = "holofy.display.rates";

export const DEFAULT_CURRENCY: DisplayCurrency = "EUR";

type CurrencyMeta = { locale: string; label: string; symbol: string };

// Locale drives grouping/decimal marks and symbol placement (€1.234,56 vs $1,234.56).
export const CURRENCY_META: Record<DisplayCurrency, CurrencyMeta> = {
  EUR: { locale: "de-DE", label: "Euro", symbol: "€" },
  USD: { locale: "en-US", label: "US Dollar", symbol: "$" },
};

// Last-resort EUR→currency rates if we have never fetched a live one and we're offline. A stale
// constant is acceptable only because a non-EUR amount is always shown as "converted" — it's a
// reading aid, not a settlement price. EUR is identity.
export const FALLBACK_RATES: Record<DisplayCurrency, number> = { EUR: 1, USD: 1.08 };

// Narrow an unknown persisted value back to a DisplayCurrency, defaulting for any legacy/corrupt
// entry so a bad storage read can never wedge the app on an invalid currency.
export function parseCurrency(value: string | null | undefined): DisplayCurrency {
  return value === "EUR" || value === "USD" ? value : DEFAULT_CURRENCY;
}

/** EUR amount → the display currency's amount at the given EUR→currency rate. */
export function convertFromEur(amountEur: number, rate: number): number {
  return amountEur * rate;
}

/** Format an EUR amount in the chosen display currency (converting first). */
export function formatFromEur(amountEur: number, currency: DisplayCurrency, rate: number): string {
  const { locale } = CURRENCY_META[currency];
  const value = convertFromEur(amountEur, rate);
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(value);
  } catch {
    // Hermes ships Intl, but guard a missing-locale build so a price still renders.
    return `${CURRENCY_META[currency].symbol}${value.toFixed(2)}`;
  }
}

export type RateResult = { rate: number; asOf: string | null };

// Fetch today's EUR→currency rate from frankfurter.app — the free, no-key ECB reference feed.
// Returns null on any network/shape failure so the caller can fall back to a cached/constant
// rate rather than throw. EUR resolves to identity without a network call.
export async function fetchEurRate(currency: DisplayCurrency): Promise<RateResult | null> {
  if (currency === "EUR") return { rate: 1, asOf: null };
  try {
    const res = await fetch(`https://api.frankfurter.app/latest?from=EUR&to=${currency}`);
    if (!res.ok) return null;
    const data = (await res.json()) as { rates?: Record<string, number>; date?: string };
    const rate = data?.rates?.[currency];
    return typeof rate === "number" && rate > 0 ? { rate, asOf: data.date ?? null } : null;
  } catch {
    return null;
  }
}
