import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createHttpClient } from "../client";
import { mapAuthSession } from "../mapping";
import type { WireAuthTokenResponse } from "../types";

const TOKEN_WIRE: WireAuthTokenResponse = {
  access_token: "header.payload.sig",
  token_type: "bearer",
  expires_in: 2_592_000,
  user: { id: "user-1", email: "collector@example.com" },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("mapAuthSession", () => {
  it("maps the token response into the app session model", () => {
    const session = mapAuthSession(TOKEN_WIRE);
    assert.equal(session.token, "header.payload.sig");
    assert.equal(session.expiresInSeconds, 2_592_000);
    assert.deepEqual(session.user, { id: "user-1", email: "collector@example.com" });
  });

  it("rejects a response with no token", () => {
    assert.throws(() => mapAuthSession({ ...TOKEN_WIRE, access_token: "" }));
  });
});

describe("http client auth", () => {
  it("register POSTs credentials to /auth/register and returns the session", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const client = createHttpClient({
      baseUrl: "https://api.test",
      getToken: () => null,
      fetchImpl: async (url, init) => {
        calls.push({ url: String(url), init });
        return jsonResponse(TOKEN_WIRE, 201);
      },
    });

    const session = await client.register({ email: "a@b.co", password: "longenough" });
    assert.equal(session.token, "header.payload.sig");
    assert.equal(calls[0]!.url, "https://api.test/auth/register");
    assert.equal(calls[0]!.init?.method, "POST");
    assert.deepEqual(JSON.parse(String(calls[0]!.init?.body)), {
      email: "a@b.co",
      password: "longenough",
    });
  });

  it("login returns the session from /auth/login", async () => {
    const client = createHttpClient({
      baseUrl: "https://api.test",
      getToken: () => null,
      fetchImpl: async () => jsonResponse(TOKEN_WIRE),
    });
    const session = await client.login({ email: "a@b.co", password: "x" });
    assert.equal(session.user.email, "collector@example.com");
  });

  it("currentUser sends the bearer and maps /auth/me", async () => {
    let sentAuth: string | null = null;
    const client = createHttpClient({
      baseUrl: "https://api.test",
      getToken: () => "live-token",
      fetchImpl: async (_url, init) => {
        sentAuth = new Headers(init?.headers).get("Authorization");
        return jsonResponse(TOKEN_WIRE.user);
      },
    });
    const account = await client.currentUser();
    assert.equal(account.email, "collector@example.com");
    assert.equal(sentAuth, "Bearer live-token");
  });

  it("surfaces a 401 as an unauthorized ApiError", async () => {
    const client = createHttpClient({
      baseUrl: "https://api.test",
      getToken: () => "bad",
      fetchImpl: async () =>
        jsonResponse({ error: { code: "unauthorized", message: "nope", details: {} } }, 401),
    });
    await assert.rejects(client.currentUser(), (err: unknown) => {
      return err instanceof Error && (err as { code?: string }).code === "unauthorized";
    });
  });
});
