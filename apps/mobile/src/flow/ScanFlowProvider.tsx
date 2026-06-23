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
  type Authenticity,
  type BatchScan,
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

// The authenticity sub-flow runs after the user captures the print + holo shots. Kept in
// the same provider as the scan so the verdict route can read the result a back-navigation
// preserves, and so the card being screened (the reveal choice) is already to hand for the
// catalog cross-check and value gate the backend needs.
type AuthenticityState =
  | { status: "idle" }
  | { status: "screening" }
  | { status: "ready"; result: Authenticity }
  | { status: "error" };

// The rapid/stack sub-flow. The user flips a pile in RapidScanScreen, then the review screen
// reads the authoritative batch result a back-navigation preserves. Kept here, alongside the
// single scan, so the review route never re-runs the batch on a back-nav and the bulk-add can
// reuse the same Vault-revision signal the single add bumps.
type BatchState =
  | { status: "idle" }
  | { status: "scanning" }
  | { status: "ready"; result: BatchScan }
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
  /** Monotonic counter bumped on every add/removal — Vault screens refetch on change. */
  vaultRevision: number;
  /** Signal that the Vault's contents changed elsewhere (e.g. a card removed from detail). */
  notifyVaultChanged: () => void;
  /** The in-flight / settled rapid-stack batch the review screen renders. */
  batch: BatchState;
  /** Run POST /scan/batch on a session's flipped capture refs; stores the deduped result. */
  runBatchScan: (captureRefs: string[]) => Promise<BatchScan | null>;
  /** Clear the batch back to idle — e.g. on leaving the review for a fresh stack. */
  resetBatch: () => void;
  /**
   * Commit a set of reviewed cards to the Vault in one pass. Returns how many landed; bumps
   * the Vault revision once so the list refetches a single time, not per card.
   */
  bulkAddToVault: (
    additions: { canonicalId: string; quantity: number }[],
    condition?: Condition
  ) => Promise<number>;
  /** The in-flight / settled pre-grade for the card the user is grading. */
  pregrade: PregradeState;
  /** Run the pre-grade on a captured multi-angle bundle; stores the estimated/retake result. */
  runPregrade: (captureRef: string) => Promise<Pregrade | null>;
  /** Clear the pre-grade back to idle — e.g. on leaving the gauge for a fresh re-scan. */
  resetPregrade: () => void;
  /** The in-flight / settled authenticity screening for the card being checked. */
  authenticity: AuthenticityState;
  /** Run the authenticity screening on a captured print+holo bundle; stores the result. */
  runAuthenticity: (captureRef: string) => Promise<Authenticity | null>;
  /** Clear the authenticity back to idle — e.g. on leaving the verdict for a fresh re-shoot. */
  resetAuthenticity: () => void;
  /**
   * The session's training-consent choice, threaded into the scan/pre-grade calls so a
   * consented capture is sent with the opt-in. Off until the user explicitly turns it on
   * (the first-capture prompt, or the privacy screen) — never implied (charter §3.5).
   */
  trainingConsent: boolean;
  /** Set the session consent choice; the first-capture prompt and privacy screen call this. */
  setTrainingConsent: (granted: boolean) => void;
  /** Whether the one-time first-capture consent prompt has been shown this session. */
  consentPromptSeen: boolean;
  /** Mark the first-capture prompt shown so it isn't offered again. */
  markConsentPromptSeen: () => void;
  reset: () => void;
};

const ScanFlowContext = createContext<ScanFlowValue | null>(null);

export function ScanFlowProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [scan, setScan] = useState<ScanState>({ status: "idle" });
  const [revealChoice, setRevealChoice] = useState<ScanChoice | null>(null);
  const [vaultRevision, setVaultRevision] = useState(0);
  const [batch, setBatch] = useState<BatchState>({ status: "idle" });
  const [pregrade, setPregrade] = useState<PregradeState>({ status: "idle" });
  const [authenticity, setAuthenticity] = useState<AuthenticityState>({ status: "idle" });
  // Off by default — the only honest default for personal-data consent (charter §3.5).
  const [trainingConsent, setTrainingConsent] = useState(false);
  const [consentPromptSeen, setConsentPromptSeen] = useState(false);

  const runScan = useCallback(
    async (bundleId: string) => {
      setScan({ status: "scanning", bundleId });
      try {
        const result = await api.scan({ bundleId, trainingConsent });
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
    [api, trainingConsent]
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

  // Bumped after a mutation the Vault list doesn't make itself — e.g. a removal from the card
  // detail. The Vault tab stays mounted behind the detail route, so without this its data is
  // stale on back-nav; the revision change retriggers its load.
  const notifyVaultChanged = useCallback(() => setVaultRevision((n) => n + 1), []);

  const runBatchScan = useCallback(
    async (captureRefs: string[]) => {
      setBatch({ status: "scanning" });
      try {
        const result = await api.batchScan({ items: captureRefs.map((bundleId) => ({ bundleId })) });
        setBatch({ status: "ready", result });
        return result;
      } catch {
        setBatch({ status: "error" });
        return null;
      }
    },
    [api]
  );

  const resetBatch = useCallback(() => setBatch({ status: "idle" }), []);

  // Bulk add commits the reviewed stack and bumps the Vault revision *once* so the Vault list
  // refetches a single time. A per-card failure is counted out rather than aborting the lot —
  // the user sees how many of their keepers landed.
  const bulkAddToVault = useCallback(
    async (
      additions: { canonicalId: string; quantity: number }[],
      condition: Condition = "near_mint"
    ) => {
      const results = await Promise.all(
        additions.map((a) =>
          api
            .addToCollection({ canonicalId: a.canonicalId, condition, quantity: a.quantity })
            .then(() => true)
            .catch(() => false)
        )
      );
      const added = results.filter(Boolean).length;
      if (added > 0) setVaultRevision((n) => n + 1);
      return added;
    },
    [api]
  );

  const runPregrade = useCallback(
    async (captureRef: string) => {
      setPregrade({ status: "assessing" });
      try {
        const result = await api.pregrade({
          captureRef,
          cardId: revealChoice?.identity.canonicalId ?? null,
          trainingConsent,
        });
        setPregrade({ status: "ready", result });
        return result;
      } catch {
        setPregrade({ status: "error" });
        return null;
      }
    },
    [api, revealChoice, trainingConsent]
  );

  const resetPregrade = useCallback(() => setPregrade({ status: "idle" }), []);

  // The authenticity endpoint requires a resolved card (the catalog cross-check + value gate
  // are meaningless without one), so this is a no-op when nothing has resolved — never a guess.
  const runAuthenticity = useCallback(
    async (captureRef: string) => {
      const cardId = revealChoice?.identity.canonicalId;
      if (!cardId) {
        setAuthenticity({ status: "error" });
        return null;
      }
      setAuthenticity({ status: "screening" });
      try {
        const result = await api.authenticity({ captureRef, cardId, trainingConsent });
        setAuthenticity({ status: "ready", result });
        return result;
      } catch {
        setAuthenticity({ status: "error" });
        return null;
      }
    },
    [api, revealChoice, trainingConsent]
  );

  const resetAuthenticity = useCallback(() => setAuthenticity({ status: "idle" }), []);
  const markConsentPromptSeen = useCallback(() => setConsentPromptSeen(true), []);

  const reset = useCallback(() => {
    setScan({ status: "idle" });
    setRevealChoice(null);
    setPregrade({ status: "idle" });
    setAuthenticity({ status: "idle" });
    setBatch({ status: "idle" });
  }, []);

  const value = useMemo<ScanFlowValue>(
    () => ({
      scan,
      revealChoice,
      runScan,
      confirmChoice,
      addToVault,
      vaultRevision,
      notifyVaultChanged,
      batch,
      runBatchScan,
      resetBatch,
      bulkAddToVault,
      pregrade,
      runPregrade,
      resetPregrade,
      authenticity,
      runAuthenticity,
      resetAuthenticity,
      trainingConsent,
      setTrainingConsent,
      consentPromptSeen,
      markConsentPromptSeen,
      reset,
    }),
    [
      scan,
      revealChoice,
      runScan,
      confirmChoice,
      addToVault,
      vaultRevision,
      notifyVaultChanged,
      batch,
      runBatchScan,
      resetBatch,
      bulkAddToVault,
      pregrade,
      runPregrade,
      resetPregrade,
      authenticity,
      runAuthenticity,
      resetAuthenticity,
      trainingConsent,
      consentPromptSeen,
      markConsentPromptSeen,
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
