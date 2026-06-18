"""A single error model for the whole API.

Every failure the client can see is a ``HolofyError`` carrying a stable machine ``code``
and an HTTP status. Handlers (registered in ``app.main``) render them — and unhandled
exceptions — into one envelope shape, so the mobile client parses errors the same way
regardless of where they originated.
"""

from __future__ import annotations

from pydantic import BaseModel


class HolofyError(Exception):
    """Base for application errors that map to a client-visible response.

    ``code`` is part of the API contract and must stay stable across releases; ``message``
    is human-facing and may change. ``details`` carries structured, non-sensitive context.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CardNotFoundError(HolofyError):
    status_code = 404
    code = "card_not_found"


class PriceUnavailableError(HolofyError):
    """Card resolved but carries no pricing — a long-tail/unlisted card, not a fault."""

    status_code = 404
    code = "price_unavailable"


class CaptureNotFoundError(HolofyError):
    """A pre-grade referenced a capture that doesn't resolve — an unknown/expired upload.

    Distinct from a gradeable-but-poor capture: that is a typed ``retake`` body with a 200,
    not an error envelope.
    """

    status_code = 404
    code = "capture_not_found"


class RecognitionFailedError(HolofyError):
    status_code = 422
    code = "recognition_failed"


class UpstreamUnavailableError(HolofyError):
    """A bought/external dependency failed or timed out — distinct from our own bugs."""

    status_code = 502
    code = "upstream_unavailable"


class NotAuthenticatedError(HolofyError):
    """No usable credential on a user-scoped path — missing or malformed bearer token."""

    status_code = 401
    code = "not_authenticated"


class InvalidCredentialError(HolofyError):
    """A bearer token was present but failed verification or named no known user."""

    status_code = 401
    code = "invalid_credential"


class QuotaExceededError(HolofyError):
    """The caller has spent its plan's quota for the window — a freemium boundary, not a
    fault. ``details`` carries the limit and the seconds until it resets so the client can
    show "resets in …" rather than a bare 429.
    """

    status_code = 429
    code = "quota_exceeded"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = {}


class ErrorResponse(BaseModel):
    """The one envelope every error response uses."""

    error: ErrorBody
