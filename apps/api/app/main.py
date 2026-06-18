"""Application factory, middleware, and exception handlers.

Wiring lives here so the app object is assembled in one readable place: providers are
built once on startup from config and closed on shutdown; every error — whether a domain
``HolofyError``, a pydantic validation failure, or an unexpected exception — is rendered
into the single ``ErrorResponse`` envelope the client parses.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    authenticity,
    collection,
    consent,
    health,
    portfolio,
    pregrade,
    scan,
)
from app.auth.factory import build_auth_provider
from app.config import Settings, get_settings
from app.core.errors import ErrorBody, ErrorResponse, HolofyError
from app.core.logging import bind_request_id, configure_logging, current_request_id
from app.datalake.factory import build_datalake_sink
from app.db.session import create_engine, create_session_factory
from app.grading.capture_store import MockCaptureStore
from app.providers.factory import (
    build_authenticity_provider,
    build_grading_provider,
    build_pricing_provider,
    build_recognition_provider,
)
from app.ratelimit.factory import build_rate_limiter

_REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("holofy.api")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.recognition_provider = build_recognition_provider(settings)
    pricing_provider, pricing_client = build_pricing_provider(settings)
    app.state.pricing_provider = pricing_provider
    app.state.pricing_client = pricing_client
    app.state.grading_provider = build_grading_provider(settings)
    app.state.authenticity_provider = build_authenticity_provider(settings)
    # The consented-capture training lake. Built once and held on state so a single sink (and
    # for the real backend, its one connection pool) is shared across requests, like a provider.
    app.state.datalake_sink = build_datalake_sink(settings)
    # Object storage for capture stills is mocked for now (synthetic captures by ref); the
    # real EU-region client drops in behind the same CaptureStore Protocol.
    app.state.capture_store = MockCaptureStore()
    app.state.auth_provider = build_auth_provider(settings)
    app.state.rate_limiter = build_rate_limiter(settings)

    engine = create_engine(settings.database_url, echo=settings.database_echo)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)

    logger.info(
        "providers initialized",
        extra={
            "recognition_provider": settings.recognition_provider,
            "pricing_provider": settings.pricing_provider,
            "grading_provider": settings.grading_provider,
            "authenticity_provider": settings.authenticity_provider,
            "auth_provider": settings.auth_provider,
            "rate_limit_provider": settings.rate_limit_provider,
        },
    )
    try:
        yield
    finally:
        if pricing_client is not None:
            await pricing_client.aclose()
        await engine.dispose()


def _error_response(
    *, status_code: int, code: str, message: str, details: dict[str, object]
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    headers = {}
    if (request_id := current_request_id()) is not None:
        headers[_REQUEST_ID_HEADER] = request_id
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HolofyError)
    async def _handle_holofy(_request: Request, exc: HolofyError) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="Request failed validation.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Log the cause server-side; never leak internals to the client.
        logger.exception("unhandled error", exc_info=exc)
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred.",
            details={},
        )


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    # Honour an inbound request id (mobile client correlation) or mint one; bind it for
    # logging and echo it back so a user-reported scan can be traced end to end.
    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):  # noqa: ANN001, ANN202
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex
        bind_request_id(request_id)
        response = await call_next(request)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response

    # Deny-by-default origins (only the configured app origins), and — with credentials on —
    # no wildcard methods/headers: a browser may only use the verbs the API actually serves
    # (GET, POST, plus the OPTIONS preflight) and send the headers it actually reads. The
    # request-id correlation header is both accepted inbound and exposed outbound.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", _REQUEST_ID_HEADER],
        expose_headers=[_REQUEST_ID_HEADER],
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, as_json=settings.log_json)

    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    _register_middleware(app, settings)
    _register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(scan.router)
    app.include_router(pregrade.router)
    app.include_router(authenticity.router)
    app.include_router(collection.router)
    app.include_router(portfolio.router)
    app.include_router(consent.router)

    return app


app = create_app()
