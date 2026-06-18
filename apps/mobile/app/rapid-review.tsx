import { useState } from "react";
import { AccessibilityInfo } from "react-native";
import { useRouter } from "expo-router";

import { useScanFlow } from "@/flow/ScanFlowProvider";
import { RapidReviewScreen } from "@/screens/rapid/RapidReviewScreen";
import { ADDED_TOAST } from "@/screens/rapid/copy";

// Confirm-at-end review for a rapid stack. Reads the batch result the flow holds, renders the
// resolved / confirm / missed / over-quota groups, and bulk-adds the selected keepers to the
// Vault in one pass. The ID+value-only boundary is explicit: a resolved card's "Grade / Check
// authenticity" re-enters the single guided capture (the scanner), where a careful multi-angle
// shot is possible — you can't grade or authenticate from a rapid flip.
export default function RapidReview() {
  const router = useRouter();
  const { batch, bulkAddToVault } = useScanFlow();
  const [busy, setBusy] = useState(false);

  return (
    <RapidReviewScreen
      batch={batch.status === "ready" ? batch.result : null}
      loading={batch.status === "scanning"}
      error={batch.status === "error"}
      busy={busy}
      onBack={() => router.back()}
      onRetry={() => {
        // The captures the user flipped are encoded in the result's refs; on a transport error
        // there's nothing to retry from, so send them back to flip the stack again.
        router.replace("/rapid");
      }}
      onBulkAdd={async (additions) => {
        if (additions.length === 0) return;
        setBusy(true);
        const added = await bulkAddToVault(additions);
        setBusy(false);
        if (added > 0) {
          AccessibilityInfo.announceForAccessibility(
            `${ADDED_TOAST} — ${added} ${added === 1 ? "card" : "cards"}`
          );
          router.replace("/");
        }
      }}
      // Grading / authenticity can't happen from a flip — re-enter the single guided scanner.
      onGrade={() => router.replace("/scan")}
      onRecapture={() => router.replace("/scan")}
    />
  );
}
