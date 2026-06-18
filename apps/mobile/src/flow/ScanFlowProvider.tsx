import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  useApi,
  type CardIdentity,
  type Condition,
  type Pregrade,
  type ScanChoice,
  type ScanResult,
} from "@/api";

// The scan → reveal/confirm → add flow's shared state. expo-router moves between the
// route files; this context carries the in-flight scan result and the add-to-Vault
// action so a screen never re-runs recognition on a back-navigation or re-serializes a
// CardIdentity through URL params. One scan lives here at a time — the last capture.

type ScanState =
  | { status: "idle" }
  | { status: "scanning"; bundleId: string }
  | { status: "ready"; bundleId: string; result: ScanResult }
  | { status: "error"; bundleId: string; message: string };

// The pre-grade sub-flow runs after the user captures a multi-angle bundle. It's kept in
// the same provider as the scan so the gauge route can read the result a back-navigation
// preserves, and so the card the pre-grade is *of* (the reveal choice) is already to hand.
type PregradeState =
  | { status: "idle" }
  | { status: "assessing" }
  | { status: "ready"; result: Pregrade }
  | { status: "error" };

type ScanFlowValue = {
  scan: ScanState;
  /**
   * The card the reveal screen should show: a resolved scan, or the choice the user
   * confirmed from the low-confidence chooser. Null until a scan resolves/confirms.
   */
  revealChoice: ScanChoice | null;
  /** Kick off recognition for a captured bundle; resolves to the outcome it stored. */
  runScan: (bundleId: string) => Promise<ScanResult | null>;
  /** Promote a confirmed disambiguation choice into the reveal slot. */
  confirmChoice: (choice: ScanChoice) => void;
  /** Commit a chosen identity to the Vault. Returns true on success. */
  addToVault: (identity: CardIdentity, condition?: Condition) => Promise<boolean>;
  /** Monotonic counter bumped on every successful add — Vault screens refetch on change. */
  vaultRevision: number;
  /** The in-flight / settled pre-grade for the card the user is grading. */
  pregrade: PregradeState;
  /** Run the pre-grade on a captured multi-angle bundle; stores the estimated/retake result. */
  runPregrade: (captureRef: string) => Promise<Pregrade | null>;
  /** Clear the pre-grade back to idle — e.g. on leaving the gauge for a fresh re-scan. */
  resetPregrade: () => void;
  reset: () => void;
};

const ScanFlowContext = createContext<ScanFlowValue | null>(null);

export function ScanFlowProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [scan, setScan] = useState<ScanState>({ status: "idle" });
  const [revealChoice, setRevealChoice] = useState<ScanChoice | null>(null);
  const [vaultRevision, setVaultRevision] = useState(0);
  const [pregrade, setPregrade] = useState<PregradeState>({ status: "idle" });

  const runScan = useCallback(
    async (bundleId: string) => {
      setScan({ status: "scanning", bundleId });
      try {
        const result = await api.scan({ bundleId });
        setScan({ status: "ready", bundleId, result });
        // A confident match goes straight to reveal; an ambiguous one waits for confirm.
        setRevealChoice(
          result.outcome === "resolved"
            ? { identity: result.identity, confidence: result.confidence, price: result.price }
            : null
        );
        return result;
      } catch (err) {
        setScan({
          status: "error",
          bundleId,
          message:
            err instanceof Error
              ? err.message
              : "We couldn't read that one — try a cleaner shot.",
        });
        return null;
      }
    },
    [api]
  );

  const addToVault = useCallback(
    async (identity: CardIdentity, condition: Condition = "near_mint") => {
      try {
        await api.addToCollection({ canonicalId: identity.canonicalId, condition });
        setVaultRevision((n) => n + 1);
        return true;
      } catch {
        return false;
      }
    },
    [api]
  );

  const confirmChoice = useCallback((choice: ScanChoice) => setRevealChoice(choice), []);

  const runPregrade = useCallback(
    async (captureRef: string) => {
      setPregrade({ status: "assessing" });
      try {
        const result = await api.pregrade({
          captureRef,
          cardId: revealChoice?.identity.canonicalId ?? null,
        });
        setPregrade({ status: "ready", result });
        return result;
      } catch {
        setPregrade({ status: "error" });
        return null;
      }
    },
    [api, revealChoice]
  );

  const resetPregrade = useCallback(() => setPregrade({ status: "idle" }), []);

  const reset = useCallback(() => {
    setScan({ status: "idle" });
    setRevealChoice(null);
    setPregrade({ status: "idle" });
  }, []);

  const value = useMemo<ScanFlowValue>(
    () => ({
      scan,
      revealChoice,
      runScan,
      confirmChoice,
      addToVault,
      vaultRevision,
      pregrade,
      runPregrade,
      resetPregrade,
      reset,
    }),
    [
      scan,
      revealChoice,
      runScan,
      confirmChoice,
      addToVault,
      vaultRevision,
      pregrade,
      runPregrade,
      resetPregrade,
      reset,
    ]
  );

  return <ScanFlowContext.Provider value={value}>{children}</ScanFlowContext.Provider>;
}

export function useScanFlow(): ScanFlowValue {
  const ctx = useContext(ScanFlowContext);
  if (!ctx) throw new Error("useScanFlow must be used within <ScanFlowProvider>.");
  return ctx;
}
