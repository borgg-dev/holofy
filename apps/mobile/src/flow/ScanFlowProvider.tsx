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
  reset: () => void;
};

const ScanFlowContext = createContext<ScanFlowValue | null>(null);

export function ScanFlowProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [scan, setScan] = useState<ScanState>({ status: "idle" });
  const [revealChoice, setRevealChoice] = useState<ScanChoice | null>(null);
  const [vaultRevision, setVaultRevision] = useState(0);

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

  const reset = useCallback(() => {
    setScan({ status: "idle" });
    setRevealChoice(null);
  }, []);

  const value = useMemo<ScanFlowValue>(
    () => ({ scan, revealChoice, runScan, confirmChoice, addToVault, vaultRevision, reset }),
    [scan, revealChoice, runScan, confirmChoice, addToVault, vaultRevision, reset]
  );

  return <ScanFlowContext.Provider value={value}>{children}</ScanFlowContext.Provider>;
}

export function useScanFlow(): ScanFlowValue {
  const ctx = useContext(ScanFlowContext);
  if (!ctx) throw new Error("useScanFlow must be used within <ScanFlowProvider>.");
  return ctx;
}
