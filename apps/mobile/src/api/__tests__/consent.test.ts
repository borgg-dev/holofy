import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { createFixtureClient, createHttpClient } from "../client";
import { resetFixtures } from "../fixtures";
import { consentedTotal, mapConsent } from "../mapping";
import type { WireConsentState } from "../types";

afterEach(() => resetFixtures());

describe("mapConsent", () => {
  it("maps the granted flag and per-kind counts", () => {
    const wire: WireConsentState = {
      granted: true,
      consented: { scans: 3, pregrades: 1, authenticity: 0 },
    };
    const c = mapConsent(wire);
    assert.equal(c.granted, true);
    assert.deepEqual(c.consented, { scans: 3, pregrades: 1, authenticity: 0 });
  });
});

describe("consentedTotal", () => {
  it("sums the per-kind counts", () => {
    assert.equal(
      consentedTotal({ granted: true, consented: { scans: 3, pregrades: 1, authenticity: 2 } }),
      6
    );
  });
  it("is zero when nothing is consented", () => {
    assert.equal(
      consentedTotal({ granted: false, consented: { scans: 0, pregrades: 0, authenticity: 0 } }),
      0
    );
  });
});

describe("fixture client — consent is off by default and revocable", () => {
  it("reads consent off for a fresh session", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const c = await client.trainingConsent();
    assert.equal(c.granted, false);
    assert.equal(consentedTotal(c), 0);
  });

  it("grants then revokes, flipping the account-level state", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const granted = await client.setTrainingConsent({ granted: true });
    assert.equal(granted.granted, true);
    assert.ok(consentedTotal(granted) > 0);

    const revoked = await client.setTrainingConsent({ granted: false });
    assert.equal(revoked.granted, false);
    assert.equal(consentedTotal(revoked), 0);
  });

  it("a consented scan raises the consented count; a default scan does not", async () => {
    const client = createFixtureClient({ latencyMs: 0 });

    // A default scan (no opt-in) leaves consent off — the privacy hard line, client-side.
    await client.scan({ bundleId: "mock-high-confidence" });
    assert.equal((await client.trainingConsent()).granted, false);

    // An explicit opt-in on the scan flips it on and is reflected in the count.
    await client.scan({ bundleId: "mock-high-confidence", trainingConsent: true });
    const after = await client.trainingConsent();
    assert.equal(after.granted, true);
    assert.equal(after.consented.scans, 1);
  });
});

describe("http client — consent never sent implicitly", () => {
  const RESOLVED_SCAN = {
    outcome: "resolved",
    card: {
      identity: {
        canonical_id: "origins-8",
        name: "Tidecaller Leviath",
        set_name: "Origins Vault",
        collector_number: "8/120",
        language: "en",
        variant: "holo",
      },
      confidence: 0.97,
      price: null,
    },
    choices: null,
    price_delta: null,
  };

  function stubFetch(captured: { path?: string; method?: string; body?: unknown }) {
    return async (url: string, init?: RequestInit): Promise<Response> => {
      captured.path = url;
      captured.method = init?.method ?? "GET";
      captured.body = init?.body ? JSON.parse(init.body as string) : undefined;
      // Reply with a shape the called endpoint's mapper accepts — these tests assert on the
      // *request* the client sent, not the response.
      const consent: WireConsentState = {
        granted: false,
        consented: { scans: 0, pregrades: 0, authenticity: 0 },
      };
      const payload = url.endsWith("/scan") ? RESOLVED_SCAN : consent;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };
  }

  it("sends training_consent=false on a scan unless explicitly opted in", async () => {
    const captured: { body?: unknown } = {};
    const client = createHttpClient({
      baseUrl: "http://x",
      getToken: () => null,
      fetchImpl: stubFetch(captured) as unknown as typeof fetch,
    });
    await client.scan({ bundleId: "b" });
    assert.equal((captured.body as { training_consent: boolean }).training_consent, false);
  });

  it("sends training_consent=true only when the caller opts in", async () => {
    const captured: { body?: unknown } = {};
    const client = createHttpClient({
      baseUrl: "http://x",
      getToken: () => null,
      fetchImpl: stubFetch(captured) as unknown as typeof fetch,
    });
    await client.scan({ bundleId: "b", trainingConsent: true });
    assert.equal((captured.body as { training_consent: boolean }).training_consent, true);
  });

  it("PUTs the consent grant with a note to /consent/training", async () => {
    const captured: { path?: string; method?: string; body?: unknown } = {};
    const client = createHttpClient({
      baseUrl: "http://x",
      getToken: () => null,
      fetchImpl: stubFetch(captured) as unknown as typeof fetch,
    });
    await client.setTrainingConsent({ granted: true, note: "privacy-screen-v1" });
    assert.ok(captured.path?.endsWith("/consent/training"));
    assert.equal(captured.method, "PUT");
    assert.deepEqual(captured.body, { granted: true, note: "privacy-screen-v1" });
  });
});
