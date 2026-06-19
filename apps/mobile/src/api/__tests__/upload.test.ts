import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createFixtureClient, createHttpClient } from "../client";

const TOKEN = () => "test-token";

describe("uploadCapture — HTTP client", () => {
  it("posts the stills as multipart and returns the server's ref + count", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const fetchImpl = (async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ ref: "abc123", image_count: 2 }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const client = createHttpClient({
      baseUrl: "https://api.holofy.test/",
      getToken: TOKEN,
      fetchImpl,
    });

    const result = await client.uploadCapture([
      { uri: "file:///front.jpg", name: "front.jpg", type: "image/jpeg" },
      { uri: "file:///back.jpg", name: "back.jpg", type: "image/jpeg" },
    ]);

    assert.deepEqual(result, { ref: "abc123", imageCount: 2 });
    assert.equal(calls.length, 1);
    const { url, init } = calls[0]!;
    assert.equal(url, "https://api.holofy.test/captures");
    assert.equal(init.method, "POST");
    // The body is FormData and we never force a JSON content-type onto a multipart upload.
    assert.ok(init.body instanceof FormData);
    const headers = init.headers as Record<string, string>;
    assert.equal(headers["Content-Type"], undefined);
    assert.equal(headers["Authorization"], "Bearer test-token");
  });

  it("surfaces a rejected upload as a typed ApiError", async () => {
    const fetchImpl = (async () =>
      new Response(
        JSON.stringify({ error: { code: "capture_rejected", message: "Not an image.", details: {} } }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      )) as unknown as typeof fetch;

    const client = createHttpClient({ baseUrl: "https://api.holofy.test", getToken: TOKEN, fetchImpl });

    await assert.rejects(
      () => client.uploadCapture([{ uri: "file:///x.txt", name: "x.txt", type: "text/plain" }]),
      (err: unknown) => (err as { code?: string }).code === "capture_rejected"
    );
  });
});

describe("uploadCapture — fixture client", () => {
  it("mints a ref offline so the capture flow runs with no server", async () => {
    const client = createFixtureClient({ latencyMs: 0 });
    const result = await client.uploadCapture([
      { uri: "file:///front.jpg", name: "front.jpg", type: "image/jpeg" },
    ]);
    assert.equal(result.imageCount, 1);
    assert.ok(result.ref.startsWith("fixture-capture-"));
  });
});
