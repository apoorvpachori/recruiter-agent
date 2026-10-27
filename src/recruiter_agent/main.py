"""Compose the application and expose the ASGI entry point."""

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.responses import Response

from recruiter_agent.api.router import api_router
from recruiter_agent.applications.service import application_service
from recruiter_agent.database import create_schema
from recruiter_agent.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


def make_lifespan(schema_initializer: Callable[[], None] = create_schema):
    """Build an app lifespan with injectable schema initialization."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """Initialize the minimal local SQLite schema at application startup."""
        schema_initializer()
        try:
            yield
        finally:
            await application_service.close_all()

    return lifespan


app = FastAPI(
    title="Recruiter Agent",
    description="A personal AI job-search copilot.",
    version="0.1.0",
    lifespan=make_lifespan(),
)
app.include_router(api_router)


@app.middleware("http")
async def log_http_request(request: Request, call_next) -> Response:
    """Log request metadata and outcome, never body, query, or URL values."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed",
            extra={
                "event": "http_request_failed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        raise

    response.headers["x-request-id"] = request_id
    logger.info(
        "http_request_completed",
        extra={
            "event": "http_request_completed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response
