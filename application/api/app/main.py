"""
Application entrypoint. WHO RUNS THIS: uvicorn — either directly in
docker-compose (this session) or as the container's entrypoint later.
WHAT IT WIRES TOGETHER: settings, logging, the correlation-ID middleware,
and every router. Every other module in this app is inert until main.py
imports and mounts it.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from ulid import ULID

from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.logging_config import correlation_id_var, setup_logging

setup_logging()  # must run before any logger is used below
logger = logging.getLogger("api.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = time.monotonic()

    # Open one connection now so the pool isn't empty when the first real
    # request (or the first readiness probe) arrives. Without this, /ready
    # can legitimately time out on its 250ms connection-acquire budget the
    # very first time it's called — proven empirically: 229.5ms cold vs
    # ~3ms once the pool is warm. Kubernetes' initialDelaySeconds covers
    # this gap too, but there's no reason to rely on that alone when
    # warming the pool here is one line.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database pool warmed")
    except Exception as exc:  # noqa: BLE001 — startup must not crash if the DB isn't up yet
        logger.warning("could not warm database pool at startup", extra={"error": str(exc)})
    logger.info(
        "startup complete",
        extra={"service": settings.service_name, "version": settings.app_version},
    )
    yield


app = FastAPI(title=settings.service_name, version=settings.app_version, lifespan=lifespan)


@app.middleware("http")
async def correlation_id_and_access_log(request: Request, call_next):
    """
    WHAT: assigns every request a correlation ID (from the inbound
    X-Request-ID header if present, otherwise generated), makes it readable
    to every log line produced while handling the request via the
    ContextVar in logging_config.py, echoes it back in the response header,
    and emits one structured access-log line per request.

    WHY a middleware and not per-endpoint code: this has to run for every
    route, including ones that don't exist yet, without each endpoint
    remembering to do it. Missing this on even one route is how "find the
    request in the logs" silently breaks for that one path.
    """
    cid = request.headers.get("X-Request-ID") or str(ULID())
    token = correlation_id_var.set(cid)
    start = time.monotonic()
    try:
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        response.headers["X-Request-ID"] = cid
        # Logged BEFORE the reset below, while correlation_id_var still
        # holds this request's id — the formatter reads it from the
        # ContextVar directly, so nothing needs passing via `extra` here.
        logger.info(
            "request handled",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    finally:
        correlation_id_var.reset(token)


from app.routers import contract, orders, products  # noqa: E402  (after app/middleware defined)

app.include_router(contract.router)
app.include_router(products.router)
app.include_router(orders.router)
