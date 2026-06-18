import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createFixtureClient } from "../client";
import { MappingError, mapBatchScan } from "../mapping";
import { STACK_BATCH } from "../fixtures";
import type { WireBatchScanResponse } from "../types";

describe("mapBatchScan — per-item outcomes", () => {
  it("maps every outcome in the canonical mixed stack", () => {
    const batch = mapBatchScan(STACK_BATCH);
    const byOutcome = batch.items.map((i) => i.outcome);
    assert.deepEqual(byOutcome, [
      "resolved",
      "resolved",
      "needs_confirmation",
      "unrecognized",
      "quota_exceeded",
    ]);
  });

  it("carries the dedupe count and the merged capture refs on a resolved item", () => {
    const batch = mapBatchScan(STACK_BATCH);
    const resolved = batch.items[0];
    assert.ok(resolved);
    if (resolved.outcome !== "resolved") return;
    // The same card flipped twice — count 2, both bundles listed in arrival order.
    assert.equal(resolved.count, 2);
    assert.deepEqual(resolved.captureRefs, ["stack-cap-1", "stack-cap-4"]);
    assert.equal(resolved.identity.canonicalId, "origins-8");
    assert.equal(resolved.price?.value, 289);
  });

  it("parses the € delta on a needs_confirmation item and keeps both choices", () => {
    const batch = mapBatchScan(STACK_BATCH);
    const confirm = batch.items.find((i) => i.outcome === "needs_confirmation");
    assert.ok(confirm);
    if (confirm!.outcome !== "needs_confirmation") return;
    assert.equal(confirm.choices.length, 2);
    assert.equal(confirm.priceDelta, 732.6);
  });

  it("maps the quota block — charged + rejected reconcile to the budget", () => {
    const batch = mapBatchScan(STACK_BATCH);
    assert.deepEqual(batch.quota, { limit: 8, charged: 6, remaining: 0, rejected: 2 });
    // The quota_exceeded item's count is the rejected figure (skipped before recognition).
    const quota = batch.items.find((i) => i.outcome === "quota_exceeded");
    assert.equal(quota?.count, batch.quota.rejected);
  });

  it("throws when a resolved item arrives without a card", () => {
    const broken: WireBatchScanResponse = {
      items: [
        { outcome: "resolved", count: 1, capture_refs: ["x"], card: null, choices: null, price_delta: null },
      ],
      quota: { limit: 8, charged: 1, remaining: 7, rejected: 0 },
    };
    assert.throws(() => mapBatchScan(broken), MappingError);
  });

  it("throws when a needs_confirmation item carries fewer than two choices", () => {
    const broken: WireBatchScanResponse = {
      items: [
        {
          outcome: "needs_confirmation",
          count: 1,
          capture_refs: ["x"],
          card: null,
          choices: [STACK_BATCH.items[2]!.choices![0]!],
          price_delta: "10.00",
        },
      ],
      quota: { limit: 8, charged: 1, remaining: 7, rejected: 0 },
    };
    assert.throws(() => mapBatchScan(broken), MappingError);
  });
});

describe("fixture client — the stack batch path", () => {
  it("returns the mixed stack with a deduped resolved card and a quota block", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const batch = await client.batchScan({
      items: ["stack-cap-1", "stack-cap-2"].map((bundleId) => ({ bundleId })),
    });
    assert.ok(batch.items.length > 0);
    assert.ok(batch.items.some((i) => i.outcome === "resolved" && i.count > 1));
    assert.ok(batch.items.some((i) => i.outcome === "unrecognized"));
    assert.ok(batch.items.some((i) => i.outcome === "quota_exceeded"));
    assert.equal(batch.quota.limit, 8);
  });
});
