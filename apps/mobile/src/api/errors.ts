// Typed client errors. Every failure a screen handles is one of these, carrying the
// backend's stable machine `code` (apps/api/app/core/errors.py) so a screen branches on
// `error.code === "price_unavailable"` rather than sniffing HTTP status or message text.

export type ApiErrorCode =
  | "card_not_found"
  | "price_unavailable"
  | "recognition_failed"
  | "upstream_unavailable"
  | "validation_error"
  | "internal_error"
  // Client-side codes the server never sends:
  | "network_error"
  | "unauthorized";

/** A failure that mapped cleanly to the backend's ErrorResponse envelope. */
export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number;
  readonly details: Record<string, unknown>;
  /** The X-Request-ID echoed back, for support correlation when present. */
  readonly requestId: string | null;

  constructor(args: {
    code: ApiErrorCode;
    status: number;
    message: string;
    details?: Record<string, unknown>;
    requestId?: string | null;
  }) {
    super(args.message);
    this.name = "ApiError";
    this.code = args.code;
    this.status = args.status;
    this.details = args.details ?? {};
    this.requestId = args.requestId ?? null;
  }
}

/** Recognition couldn't read the capture at all → route back to scan, don't reveal. */
export function isRecognitionFailure(e: unknown): e is ApiError {
  return e instanceof ApiError && e.code === "recognition_failed";
}

/** The connection itself failed (offline, DNS, timeout) — distinct from a server error. */
export function isOffline(e: unknown): e is ApiError {
  return e instanceof ApiError && e.code === "network_error";
}
