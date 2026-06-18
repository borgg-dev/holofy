import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { BatchScanItem, CardIdentity, PriceQuote } from "@/api";
import {
  applyCapture,
  allCaptureRefs,
  entryCount,
  groupReview,
  reviewKey,
  selectedAdditions,
  stripTotals,
  type CaptureRead,
  type StripEntry,
} from "../stack";

const identity = (canonicalId: string, name = canonicalId): CardIdentity => ({
  canonicalId,
  name,
  setName: "Origins Vault",
  collectorNumber: "8/120",
  language: "en",
  variant: "holo",
});

const price = (value: number): PriceQuote => ({
  canonicalId: "x",
  currency: "EUR",
  value,
  basis: "trend",
  low: null,
  avg30: null,
  source: "cardmarket",
  asOf: new Date(),
  ageHours: 0,
  listingUrl: null,
});

const identified = (id: string, value: number | null): CaptureRead => ({
  kind: "identified",
  identity: identity(id),
  price: value == null ? null : price(value),
});

/** Run a sequence of flips through applyCapture and return the final strip. */
function flip(seq: { ref: string; read: CaptureRead }[]): StripEntry[] {
  return seq.reduce<StripEntry[]>(
    (strip, { ref, read }) => applyCapture(strip, ref, read).strip,
    []
  );
}

describe("applyCapture — dedupe merge", () => {
  it("appends a new card as its own row", () => {
    const r = applyCapture([], "cap-1", identified("a", 10));
    assert.equal(r.effect, "added");
    assert.equal(r.strip.length, 1);
    assert.deepEqual(r.entry.captureRefs, ["cap-1"]);
  });

  it("merges a re-flip of the same card onto the existing row, not a duplicate", () => {
    const first = applyCapture([], "cap-1", identified("a", 10));
    const second = applyCapture(first.strip, "cap-2", identified("a", 10));
    assert.equal(second.effect, "merged");
    assert.equal(second.strip.length, 1);
    assert.equal(entryCount(second.entry), 2);
    assert.deepEqual(second.entry.captureRefs, ["cap-1", "cap-2"]);
  });

  it("keeps distinct cards on distinct rows", () => {
    const strip = flip([
      { ref: "c1", read: identified("a", 10) },
      { ref: "c2", read: identified("b", 20) },
    ]);
    assert.equal(strip.length, 2);
  });

  it("never merges pending or unreadable flips — each is its own row", () => {
    const strip = flip([
      { ref: "c1", read: { kind: "pending" } },
      { ref: "c2", read: { kind: "pending" } },
      { ref: "c3", read: { kind: "unreadable" } },
    ]);
    assert.equal(strip.length, 3);
  });

  it("does not mutate the input strip (pure)", () => {
    const before = flip([{ ref: "c1", read: identified("a", 10) }]);
    const snapshot = JSON.parse(JSON.stringify(before));
    applyCapture(before, "c2", identified("a", 10));
    assert.deepEqual(JSON.parse(JSON.stringify(before)), snapshot);
  });
});

describe("stripTotals — running count and € total", () => {
  it("counts distinct cards, sums unit price × times flipped", () => {
    const strip = flip([
      { ref: "c1", read: identified("a", 100) },
      { ref: "c2", read: identified("a", 100) }, // merge → ×2
      { ref: "c3", read: identified("b", 50) },
    ]);
    const t = stripTotals(strip);
    assert.equal(t.cardCount, 2); // a, b
    assert.equal(t.captureCount, 3); // three flips
    assert.equal(t.totalEur, 250); // 100×2 + 50
    assert.equal(t.unpricedCount, 0);
  });

  it("excludes pending and unreadable flips from the count and total", () => {
    const strip = flip([
      { ref: "c1", read: identified("a", 100) },
      { ref: "c2", read: { kind: "pending" } },
      { ref: "c3", read: { kind: "unreadable" } },
    ]);
    const t = stripTotals(strip);
    assert.equal(t.cardCount, 1);
    assert.equal(t.totalEur, 100);
    assert.equal(t.captureCount, 3);
  });

  it("counts an identified-but-unpriced card without adding to the total", () => {
    const strip = flip([{ ref: "c1", read: identified("a", null) }]);
    const t = stripTotals(strip);
    assert.equal(t.cardCount, 1);
    assert.equal(t.unpricedCount, 1);
    assert.equal(t.totalEur, 0);
  });

  it("rounds the total to cents (no float drift across merges)", () => {
    const strip = flip([
      { ref: "c1", read: identified("a", 0.1) },
      { ref: "c2", read: identified("a", 0.1) },
      { ref: "c3", read: identified("b", 0.2) },
    ]);
    assert.equal(stripTotals(strip).totalEur, 0.4);
  });

  it("flattens every flip's refs for the batch payload, in order", () => {
    const strip = flip([
      { ref: "c1", read: identified("a", 10) },
      { ref: "c2", read: identified("b", 20) },
      { ref: "c3", read: identified("a", 10) }, // merges onto c1's row
    ]);
    assert.deepEqual(allCaptureRefs(strip), ["c1", "c3", "c2"]);
  });
});

// ── Review grouping + selection ────────────────────────────────────────────────

const resolvedItem = (ref: string, id: string, count = 1): BatchScanItem => ({
  outcome: "resolved",
  count,
  captureRefs: [ref],
  identity: identity(id),
  confidence: 0.95,
  price: price(100),
});

const confirmItem = (ref: string): BatchScanItem => ({
  outcome: "needs_confirmation",
  count: 1,
  captureRefs: [ref],
  choices: [
    { identity: identity("hi", "High"), confidence: 0.6, price: price(700) },
    { identity: identity("lo", "Low"), confidence: 0.56, price: price(20) },
  ],
  priceDelta: 680,
});

describe("groupReview — four review sections", () => {
  it("splits a mixed batch by outcome, preserving order within each group", () => {
    const groups = groupReview([
      resolvedItem("r1", "a"),
      confirmItem("c1"),
      { outcome: "unrecognized", count: 1, captureRefs: ["u1"] },
      { outcome: "quota_exceeded", count: 2, captureRefs: ["q1", "q2"] },
      resolvedItem("r2", "b"),
    ]);
    assert.equal(groups.resolved.length, 2);
    assert.equal(groups.needsConfirmation.length, 1);
    assert.equal(groups.unrecognized.length, 1);
    assert.equal(groups.quotaExceeded.length, 1);
    assert.deepEqual(
      groups.resolved.map((i) => i.identity.canonicalId),
      ["a", "b"]
    );
  });
});

describe("selectedAdditions — the bulk-add payload", () => {
  const groups = groupReview([resolvedItem("r1", "a", 2), resolvedItem("r2", "b"), confirmItem("c1")]);

  it("queues selected resolved cards with their flip-count as quantity", () => {
    const additions = selectedAdditions(groups, new Set(["r1"]), new Map([["c1", null]]));
    assert.deepEqual(additions, [{ canonicalId: "a", quantity: 2 }]);
  });

  it("includes a confirmed variant by the chosen index, with the right canonical id", () => {
    const additions = selectedAdditions(groups, new Set(["r1", "r2"]), new Map([["c1", 0]]));
    assert.deepEqual(additions, [
      { canonicalId: "a", quantity: 2 },
      { canonicalId: "b", quantity: 1 },
      { canonicalId: "hi", quantity: 1 },
    ]);
  });

  it("never banks an undecided confirmation card (no silent guess)", () => {
    const additions = selectedAdditions(groups, new Set(["r1"]), new Map([["c1", null]]));
    assert.ok(!additions.some((a) => a.canonicalId === "hi" || a.canonicalId === "lo"));
  });

  it("excludes a deselected resolved card", () => {
    const additions = selectedAdditions(groups, new Set(["r2"]), new Map([["c1", 1]]));
    assert.deepEqual(additions, [
      { canonicalId: "b", quantity: 1 },
      { canonicalId: "lo", quantity: 1 },
    ]);
  });

  it("keys selection state by the item's first capture ref", () => {
    assert.equal(reviewKey(resolvedItem("r9", "z")), "r9");
  });
});
