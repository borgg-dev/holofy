// The API client the app talks to. One interface, two implementations: a real HTTP
// client (apps/api) and a fixture client (no server). Screens depend on the interface
// via the ApiProvider context, so swapping between them — or pointing at staging — is a
// config change, never a screen change.

import { authHeader, type TokenProvider } from "./auth";
import { ApiError, type ApiErrorCode } from "./errors";
import {
  fixtureAddToCollection,
  fixtureCollection,
  fixtureNoteConsentedPregrade,
  fixtureNoteConsentedScan,
  fixturePortfolio,
  fixtureSetTrainingConsent,
  fixtureTrainingConsent,
  pregradeFixtureFor,
  scanFixtureFor,
} from "./fixtures";
import {
  mapCollectionItem,
  mapConsent,
  mapPortfolio,
  mapPregrade,
  mapScanResponse,
} from "./mapping";
import type {
  CollectionItem,
  Condition,
  Portfolio,
  Pregrade,
  ScanResult,
  TrainingConsent,
} from "./models";
import type {
  WireCollectionItem,
  WireConsentState,
  WireErrorResponse,
  WirePortfolio,
  WirePregradeResponse,
  WireScanResponse,
} from "./types";

export type ScanRequest = {
  bundleId: string;
  imageCount?: number;
  /** Opt this capture into the training lake. Off unless explicitly set (GDPR, charter §3.5). */
  trainingConsent?: boolean;
};

export type AddToCollectionRequest = {
  canonicalId: string;
  condition: Condition;
  quantity?: number;
  acquiredPriceEur?: number | null;
};

export type PregradeRequest = {
  /** Reference to the already-uploaded multi-angle capture bundle. */
  captureRef: string;
  /** Catalog card this capture is of, when a scan already resolved it. */
  cardId?: string | null;
  /** Opt this capture into the training lake. Off unless explicitly set (GDPR, charter §3.5). */
  trainingConsent?: boolean;
};

export type SetConsentRequest = {
  /** `true` opts the account into training-data use; `false` revokes it. */
  granted: boolean;
  /** The surface/copy version the choice was made under, for the server's audit trail. */
  note?: string;
};

export interface HolofyClient {
  scan(req: ScanRequest): Promise<ScanResult>;
  addToCollection(req: AddToCollectionRequest): Promise<CollectionItem>;
  listCollection(): Promise<CollectionItem[]>;
  portfolio(): Promise<Portfolio>;
  /** Honest pre-grade: an `estimated` range + sub-scores, or a `retake` with reasons. */
  pregrade(req: PregradeRequest): Promise<Pregrade>;
  /** The account's current training-consent posture — off by default. */
  trainingConsent(): Promise<TrainingConsent>;
  /** Grant or revoke training-data consent; returns the resulting posture. */
  setTrainingConsent(req: SetConsentRequest): Promise<TrainingConsent>;
}

// ── HTTP implementation ──────────────────────────────────────────────────────

const REQUEST_ID_HEADER = "X-Request-ID";

export type HttpClientConfig = {
  baseUrl: string;
  getToken: TokenProvider;
  /** Injectable for tests; defaults to global fetch in the RN runtime. */
  fetchImpl?: typeof fetch;
};

export function createHttpClient(config: HttpClientConfig): HolofyClient {
  const fetchImpl = config.fetchImpl ?? fetch;
  const base = config.baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
      res = await fetchImpl(`${base}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...authHeader(config.getToken),
          ...init?.headers,
        },
      });
    } catch (cause) {
      // A thrown fetch is a transport failure (offline, DNS, abort) — not a server
      // response. Surface it as a typed offline error the UI can show as such.
      throw new ApiError({
        code: "network_error",
        status: 0,
        message: "Couldn't reach Holofy. Check your connection and try again.",
      });
    }

    const requestId = res.headers.get(REQUEST_ID_HEADER);
    if (!res.ok) {
      throw await toApiError(res, requestId);
    }
    return (await res.json()) as T;
  }

  return {
    async scan({ bundleId, imageCount = 1, trainingConsent = false }) {
      const wire = await request<WireScanResponse>("/scan", {
        method: "POST",
        body: JSON.stringify({
          bundle_id: bundleId,
          image_count: imageCount,
          // Only sent as opt-in; the server defaults it off, so omitting it never consents.
          training_consent: trainingConsent,
        }),
      });
      return mapScanResponse(wire);
    },

    async addToCollection({ canonicalId, condition, quantity, acquiredPriceEur }) {
      const wire = await request<WireCollectionItem>("/collection", {
        method: "POST",
        body: JSON.stringify({
          canonical_id: canonicalId,
          condition,
          quantity,
          acquired_price_eur: acquiredPriceEur == null ? null : acquiredPriceEur.toFixed(2),
        }),
      });
      return mapCollectionItem(wire);
    },

    async listCollection() {
      const wire = await request<WireCollectionItem[]>("/collection");
      return wire.map(mapCollectionItem);
    },

    async portfolio() {
      const wire = await request<WirePortfolio>("/portfolio");
      return mapPortfolio(wire);
    },

    async pregrade({ captureRef, cardId, trainingConsent = false }) {
      const wire = await request<WirePregradeResponse>("/pregrade", {
        method: "POST",
        body: JSON.stringify({
          capture_ref: captureRef,
          card_id: cardId ?? null,
          training_consent: trainingConsent,
        }),
      });
      return mapPregrade(wire);
    },

    async trainingConsent() {
      const wire = await request<WireConsentState>("/consent/training");
      return mapConsent(wire);
    },

    async setTrainingConsent({ granted, note }) {
      const wire = await request<WireConsentState>("/consent/training", {
        method: "PUT",
        body: JSON.stringify({ granted, note: note ?? null }),
      });
      return mapConsent(wire);
    },
  };
}

const KNOWN_CODES: ReadonlySet<string> = new Set<ApiErrorCode>([
  "card_not_found",
  "price_unavailable",
  "recognition_failed",
  "upstream_unavailable",
  "validation_error",
  "internal_error",
]);

async function toApiError(res: Response, requestId: string | null): Promise<ApiError> {
  if (res.status === 401 || res.status === 403) {
    return new ApiError({
      code: "unauthorized",
      status: res.status,
      message: "Your session needs a refresh.",
      requestId,
    });
  }
  // Every error the backend emits wraps in the ErrorResponse envelope; tolerate a
  // non-JSON body (a proxy 502) by falling back to a generic internal error.
  try {
    const body = (await res.json()) as Partial<WireErrorResponse>;
    const err = body.error;
    const code = err && KNOWN_CODES.has(err.code) ? (err.code as ApiErrorCode) : "internal_error";
    return new ApiError({
      code,
      status: res.status,
      message: err?.message ?? "Something went wrong.",
      details: err?.details ?? {},
      requestId,
    });
  } catch {
    return new ApiError({
      code: "internal_error",
      status: res.status,
      message: "Something went wrong.",
      requestId,
    });
  }
}

// ── Fixture implementation ───────────────────────────────────────────────────

export type FixtureClientConfig = {
  /** Simulated round-trip latency so loading states are visible in the demo. */
  latencyMs?: number;
};

export function createFixtureClient(config: FixtureClientConfig = {}): HolofyClient {
  const latency = config.latencyMs ?? 450;
  const wait = () => new Promise<void>((resolve) => setTimeout(resolve, latency));

  return {
    async scan({ bundleId, trainingConsent = false }) {
      await wait();
      if (trainingConsent) fixtureNoteConsentedScan();
      return mapScanResponse(scanFixtureFor(bundleId));
    },
    async addToCollection({ canonicalId, condition, quantity }) {
      await wait();
      return mapCollectionItem(fixtureAddToCollection(canonicalId, condition, quantity));
    },
    async listCollection() {
      await wait();
      return fixtureCollection().map(mapCollectionItem);
    },
    async portfolio() {
      await wait();
      return mapPortfolio(fixturePortfolio());
    },
    async pregrade({ captureRef, trainingConsent = false }) {
      // Pre-grade assesses four factors — give it a beat longer than a price lookup so
      // the staged "Assessing…" copy is visible rather than a flash.
      await new Promise<void>((resolve) => setTimeout(resolve, latency * 2));
      if (trainingConsent) fixtureNoteConsentedPregrade();
      return mapPregrade(pregradeFixtureFor(captureRef));
    },

    async trainingConsent() {
      await wait();
      return mapConsent(fixtureTrainingConsent());
    },

    async setTrainingConsent({ granted }) {
      await wait();
      return mapConsent(fixtureSetTrainingConsent(granted));
    },
  };
}
