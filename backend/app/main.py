from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.session import dispose_engine
from app.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


async def request_context_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started_at = perf_counter()
    try:
        rejected = _reject_oversized_enrichment_request(request)
        if rejected is not None:
            rejected.headers["x-request-id"] = request_id
            return rejected
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        return response
    finally:
        structlog.contextvars.clear_contextvars()


def _reject_oversized_enrichment_request(request: Request) -> JSONResponse | None:
    if not request.url.path.endswith(("/enrichment/import", "/enrichment/preview")):
        return None
    content_length = request.headers.get("content-length")
    try:
        received = int(content_length) if content_length is not None else 0
    except ValueError:
        received = 0
    limit = request.app.state.settings.enrichment_max_request_bytes
    if received <= limit:
        return None
    return JSONResponse(
        status_code=413,
        content={
            "error": {
                "code": "enrichment_payload_too_large",
                "message": "Enrichment request body exceeds the configured limit.",
                "details": {"max_bytes": limit},
                "request_id": request.state.request_id,
            }
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.debug)

    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.middleware("http")(request_context_middleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=resolved_settings.api_prefix)
    register_exception_handlers(application)
    return application


app = create_app()
