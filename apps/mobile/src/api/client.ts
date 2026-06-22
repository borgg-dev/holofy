// The API client the app talks to. One interface, two implementations: a real HTTP
// client (apps/api) and a fixture client (no server). Screens depend on the interface
// via the ApiProvider context, so swapping between them — or pointing at staging — is a
// config change, never a screen change.

import { authHeader, type TokenProvider } from "./auth";
import { ApiError, type ApiErrorCode } from "./errors";
import {
  authenticityFixtureFor,
  batchScanFixture,
  fixtureAddToCollection,
  fixtureRemoveFromCollection,
  fixtureCollection,
  fixtureNoteConsentedAuthenticity,
  fixtureNoteConsentedPregrade,
  fixtureNoteConsentedScan,
  fixturePortfolio,
  fixtureSetTrainingConsent,
  fixtureTrainingConsent,
  pregradeFixtureFor,
  scanFixtureFor,
} from "./fixtures";
import {
  mapAuthSession,
  mapAuthUser,
  mapAuthenticity,
  mapBatchScan,
  mapCollectionItem,
  mapConsent,
  mapPortfolio,
  mapPregrade,
  mapScanResponse,
} from "./mapping";
import type {
  AuthAccount,
  AuthSession,
  Authenticity,
  BatchScan,
  CollectionItem,
  Condition,
  Credentials,
  Portfolio,
  Pregrade,
  ScanResult,
  TrainingConsent,
} from "./models";
import type {
  WireAuthTokenResponse,
  WireAuthUser,
  WireAuthenticityResponse,
  WireBatchScanResponse,
  WireCaptureUploadResponse,
  WireCollectionItem,
  WireConsentState,
  WireErrorResponse,
  WirePortfolio,
  WirePregradeResponse,
  WireScanResponse,
} from "./types";

/** One still to upload — the shape React Native's FormData accepts for a file part. */
export type CaptureImage = {
  /** Local file URI from the camera (e.g. takePictureAsync's `uri`). */
  uri: string;
  name: string;
  /** MIME type — must be one the server accepts (image/jpeg | image/png | image/webp). */
  type: string;
};

/** The reference a successful upload returns — passed back as a scan/pre-grade ref. */
export type CaptureUpload = {
  ref: string;
  imageCount: number;
};

export type ScanRequest = {
  bundleId: string;
  imageCount?: number;
  /** Opt this capture into the training lake. Off unless explicitly set (GDPR, charter §3.5). */
  trainingConsent?: boolean;
};

export type BatchScanRequest = {
  /** One bundle ref per detected card, in flip order. Capped server-side (MAX_BATCH_ITEMS=50). */
  items: { bundleId: string; imageCount?: number }[];
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

export type AuthenticityRequest = {
  /** Reference to the already-uploaded authenticity capture (print close-up + holo tilt). */
  captureRef: string;
  /** Catalog card this capture is of — required for the catalog cross-check + value gate. */
  cardId: string;
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
  /** Create a password account and return the session (token + account). */
  register(credentials: Credentials): Promise<AuthSession>;
  /** Verify a password and return the session (token + account). */
  login(credentials: Credentials): Promise<AuthSession>;
  /** The account the current bearer resolves to — used to validate a stored token on launch. */
  currentUser(): Promise<AuthAccount>;
  /** Permanently erase the signed-in account and all its data (GDPR). The bearer dies with it. */
  deleteAccount(): Promise<void>;
  /**
   * Upload a card's stills and get back the reference the scan/pre-grade calls carry. The
   * first step of every real (non-fixture) capture: bytes go up once, here, and never ride
   * along with the later recognition/grading requests (data minimization, charter §3.5).
   */
  uploadCapture(images: CaptureImage[]): Promise<CaptureUpload>;
  scan(req: ScanRequest): Promise<ScanResult>;
  /**
   * Stack mode: a pile of captures in, deduped per-card results out. ID + value only —
   * the response carries no grade/authenticity, and the quota block reports the COGS.
   */
  batchScan(req: BatchScanRequest): Promise<BatchScan>;
  addToCollection(req: AddToCollectionRequest): Promise<CollectionItem>;
  /** Remove one holding from the Vault by its id. Idempotent from the user's view. */
  removeFromCollection(id: string): Promise<void>;
  listCollection(): Promise<CollectionItem[]>;
  portfolio(): Promise<Portfolio>;
  /** Honest pre-grade: an `estimated` range + sub-scores, or a `retake` with reasons. */
  pregrade(req: PregradeRequest): Promise<Pregrade>;
  /**
   * Private authenticity screening: an `assessed` risk band + per-signal reads, a `retake`
   * (poor capture), or `notAssessed` (below the value threshold). Never a fake/genuine verdict.
   */
  authenticity(req: AuthenticityRequest): Promise<Authenticity>;
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
    // A multipart upload sets its own Content-Type (with the boundary); forcing JSON here
    // would corrupt it, so the header is only defaulted for JSON bodies.
    const isMultipart = init?.body instanceof FormData;
    let res: Response;
    try {
      res = await fetchImpl(`${base}${path}`, {
        ...init,
        headers: {
          ...(isMultipart ? {} : { "Content-Type": "application/json" }),
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
    // A 204 (e.g. account deletion) carries no body — don't try to parse one.
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  return {
    async register({ email, password }) {
      const wire = await request<WireAuthTokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      return mapAuthSession(wire);
    },

    async login({ email, password }) {
      const wire = await request<WireAuthTokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      return mapAuthSession(wire);
    },

    async currentUser() {
      const wire = await request<WireAuthUser>("/auth/me");
      return mapAuthUser(wire);
    },

    async deleteAccount() {
      await request<void>("/auth/me", { method: "DELETE" });
    },

    async uploadCapture(images) {
      const form = new FormData();
      for (const image of images) {
        // RN's FormData takes a `{ uri, name, type }` file part, which the DOM lib types as
        // Blob; the cast is the standard React Native idiom for a local-file upload.
        form.append("files", { uri: image.uri, name: image.name, type: image.type } as unknown as Blob);
      }
      const wire = await request<WireCaptureUploadResponse>("/captures", {
        method: "POST",
        body: form,
      });
      return { ref: wire.ref, imageCount: wire.image_count };
    },

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

    async batchScan({ items }) {
      const wire = await request<WireBatchScanResponse>("/scan/batch", {
        method: "POST",
        body: JSON.stringify({
          items: items.map((it) => ({
            bundle_id: it.bundleId,
            ...(it.imageCount == null ? {} : { image_count: it.imageCount }),
          })),
        }),
      });
      return mapBatchScan(wire);
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

    async removeFromCollection(id) {
      await request<void>(`/collection/${id}`, { method: "DELETE" });
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

    async authenticity({ captureRef, cardId, trainingConsent = false }) {
      const wire = await request<WireAuthenticityResponse>("/authenticity", {
        method: "POST",
        body: JSON.stringify({
          capture_ref: captureRef,
          card_id: cardId,
          training_consent: trainingConsent,
        }),
      });
      return mapAuthenticity(wire);
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
  "capture_rejected",
  "capture_upload_unavailable",
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

// Demo references the fixture cycles through, so a sequence of captures shows both scan
// outcomes (a confident resolve, then an ambiguous confirm) — the variety the live recognizer
// produces from real cards. scanFixtureFor maps these to the matching fixtures.
const _DEMO_CAPTURE_REFS = ["mock-high-confidence", "mock-needs-confirmation"] as const;

export function createFixtureClient(config: FixtureClientConfig = {}): HolofyClient {
  const latency = config.latencyMs ?? 450;
  const wait = () => new Promise<void>((resolve) => setTimeout(resolve, latency));
  let captureSeq = 0;

  const demoUser = { id: "demo-collector", email: "demo@holofy.app" };
  return {
    async register({ email }) {
      await wait();
      return { token: "fixture-session", expiresInSeconds: 86_400, user: { ...demoUser, email } };
    },
    async login({ email }) {
      await wait();
      return { token: "fixture-session", expiresInSeconds: 86_400, user: { ...demoUser, email } };
    },
    async currentUser() {
      await wait();
      return demoUser;
    },
    async deleteAccount() {
      await wait();
    },

    async uploadCapture(images) {
      // No bytes leave the device in the demo path — the fixture mints a reference so the
      // capture→upload→scan flow runs end to end offline, exactly as it will against the
      // server, cycling the demo refs so both scan outcomes are reachable.
      await wait();
      const ref = _DEMO_CAPTURE_REFS[captureSeq++ % _DEMO_CAPTURE_REFS.length]!;
      return { ref, imageCount: Math.max(1, images.length) };
    },
    async scan({ bundleId, trainingConsent = false }) {
      await wait();
      if (trainingConsent) fixtureNoteConsentedScan();
      return mapScanResponse(scanFixtureFor(bundleId));
    },
    async batchScan() {
      // A stack settles a touch slower than a single scan — the server recognizes each
      // capture — so give the review's "Reading the stack…" state a beat to be seen.
      await new Promise<void>((resolve) => setTimeout(resolve, latency * 2));
      return mapBatchScan(batchScanFixture());
    },
    async addToCollection({ canonicalId, condition, quantity }) {
      await wait();
      return mapCollectionItem(fixtureAddToCollection(canonicalId, condition, quantity));
    },
    async removeFromCollection(id) {
      await wait();
      fixtureRemoveFromCollection(id);
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

    async authenticity({ captureRef, trainingConsent = false }) {
      // Screening reads several independent signals — give it the same beat as pre-grade
      // so the staged "Screening…" copy is seen, not flashed.
      await new Promise<void>((resolve) => setTimeout(resolve, latency * 2));
      if (trainingConsent) fixtureNoteConsentedAuthenticity();
      return mapAuthenticity(authenticityFixtureFor(captureRef));
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
