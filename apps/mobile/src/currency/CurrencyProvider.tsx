import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  CURRENCY_META,
  CURRENCY_STORAGE_KEY,
  DEFAULT_CURRENCY,
  FALLBACK_RATES,
  RATE_CACHE_STORAGE_KEY,
  convertFromEur,
  fetchEurRate,
  formatFromEur,
  parseCurrency,
  type DisplayCurrency,
} from "./currency";

type CurrencyContextValue = {
  /** The chosen display currency. EUR is the source of truth; others are converted. */
  currency: DisplayCurrency;
  /** Set and persist the display currency; the whole app re-formats immediately. */
  setCurrency: (currency: DisplayCurrency) => void;
  /** Convert an EUR amount to the display currency at the current rate. */
  convert: (amountEur: number) => number;
  /** Format an EUR amount in the display currency (converting first). */
  format: (amountEur: number) => string;
  /** True when the displayed currency is a conversion of EUR (so the UI can say so). */
  isConverted: boolean;
  /** The EUR→currency rate in use (1 for EUR), and the date it was published (null = fallback). */
  rate: number;
  rateAsOf: string | null;
};

// Default value = EUR identity, so any consumer rendered outside a provider (tests, the demo
// shell) still formats correctly instead of crashing — a display primitive must never throw.
const DEFAULT_VALUE: CurrencyContextValue = {
  currency: DEFAULT_CURRENCY,
  setCurrency: () => {},
  convert: (amountEur) => amountEur,
  format: (amountEur) => formatFromEur(amountEur, DEFAULT_CURRENCY, 1),
  isConverted: false,
  rate: 1,
  rateAsOf: null,
};

const CurrencyContext = createContext<CurrencyContextValue>(DEFAULT_VALUE);

type CachedRates = Record<string, { rate: number; asOf: string | null }>;

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrencyState] = useState<DisplayCurrency>(DEFAULT_CURRENCY);
  const [rates, setRates] = useState<CachedRates>({});

  // Hydrate the saved preference and any cached rates once on mount. EUR renders first; if a
  // different currency was stored, the app re-formats on this resolve — a brief EUR flash is
  // acceptable and avoids blocking first paint on a storage read.
  useEffect(() => {
    let mounted = true;
    AsyncStorage.multiGet([CURRENCY_STORAGE_KEY, RATE_CACHE_STORAGE_KEY])
      .then((pairs) => {
        if (!mounted) return;
        const map = Object.fromEntries(pairs);
        setCurrencyState(parseCurrency(map[CURRENCY_STORAGE_KEY]));
        const cached = map[RATE_CACHE_STORAGE_KEY];
        if (cached) {
          try {
            setRates(JSON.parse(cached) as CachedRates);
          } catch {
            // A corrupt cache just means we refetch; never a reason to crash.
          }
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  // Refresh the live rate whenever a non-EUR currency is active (and on first mount). A failure
  // keeps the cached/fallback rate — conversion degrades, it never breaks.
  useEffect(() => {
    if (currency === "EUR") return;
    let mounted = true;
    fetchEurRate(currency).then((result) => {
      if (!mounted || !result) return;
      setRates((prev) => {
        const next = { ...prev, [currency]: { rate: result.rate, asOf: result.asOf } };
        void AsyncStorage.setItem(RATE_CACHE_STORAGE_KEY, JSON.stringify(next)).catch(() => {});
        return next;
      });
    });
    return () => {
      mounted = false;
    };
  }, [currency]);

  const setCurrency = useCallback((next: DisplayCurrency) => {
    setCurrencyState(next);
    void AsyncStorage.setItem(CURRENCY_STORAGE_KEY, next).catch(() => {});
  }, []);

  const value = useMemo<CurrencyContextValue>(() => {
    const rate = currency === "EUR" ? 1 : rates[currency]?.rate ?? FALLBACK_RATES[currency];
    return {
      currency,
      setCurrency,
      convert: (amountEur: number) => convertFromEur(amountEur, rate),
      format: (amountEur: number) => formatFromEur(amountEur, currency, rate),
      isConverted: currency !== "EUR",
      rate,
      rateAsOf: currency === "EUR" ? null : rates[currency]?.asOf ?? null,
    };
  }, [currency, rates, setCurrency]);

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency(): CurrencyContextValue {
  return useContext(CurrencyContext);
}

export { CURRENCY_META };
