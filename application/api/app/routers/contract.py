"""
The standard operational contract every project in this lab depends on.
See docs/projects/00-reference-app/spec.md §3.

/health and /info need no database. /ready is the one endpoint that's
genuinely allowed to touch Postgres. /metrics, /work and /error-test still
follow later.
"""

import asyncio
import os
import socket
import time
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_factory

router = APIRouter()

_HOSTNAME = os.environ.get("HOSTNAME") or socket.gethostname()

# alembic/ sits two levels up from this file (app/routers/contract.py ->
# app/ -> application/api/ -> alembic/). Read once at import time — the
# migration files don't change while the process is running.
_ALEMBIC_DIR = Path(__file__).resolve().parent.parent.parent / "alembic"


def _expected_head_revision() -> str | None:
    """What migration SHOULD the database be at, according to the files
    shipped in this image? Reads the migration files directly, not the
    database — this is "the head revision compiled into the image" from
    the spec, not something that could drift out from under us at runtime.
    """
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    return ScriptDirectory.from_config(cfg).get_current_head()


@router.get("/health")
async def health(request: Request):
    """
    Liveness only. Spec §3.1: must NEVER touch Postgres or any network
    dependency — restarting this container never fixes a database outage,
    so checking the database here would only turn a recoverable dependency
    problem into a self-inflicted total outage via the kubelet's restart
    loop. Deliberately just proves the event loop can respond.
    """
    uptime = time.monotonic() - request.app.state.start_time
    return {
        "status": "alive",
        "service": settings.service_name,
        "uptime_seconds": round(uptime, 1),
    }


@router.get("/ready")
async def ready(response: Response):
    """
    Readiness. Spec §3.2 — unlike /health, this ALWAYS checks the real
    database, because "can't reach Postgres" genuinely means "don't send me
    traffic". Whole check must finish within ready_timeout_ms (500ms
    default); the connection step alone gets a tighter 250ms budget nested
    inside that, so a slow-to-acquire connection fails fast rather than
    eating the entire budget before we even get to the query.

    Always returns 200 or 503 — never 500. A raised exception here would
    tell Kubernetes "this endpoint itself is broken", when the real
    situation is just "the dependency is down", which is a 503 by
    definition.
    """
    checks: dict = {}
    healthy = True

    try:
        async with asyncio.timeout(settings.ready_timeout_ms / 1000):
            async with async_session_factory() as session:
                db_start = time.monotonic()
                try:
                    async with asyncio.timeout(0.25):
                        await session.execute(text("SELECT 1"))
                except TimeoutError:
                    checks["database"] = {
                        "status": "fail",
                        "error": "connection acquire timeout after 250ms",
                    }
                    checks["migrations"] = {"status": "skipped"}
                    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                    return {"status": "not_ready", "checks": checks}

                checks["database"] = {
                    "status": "ok",
                    "latency_ms": round((time.monotonic() - db_start) * 1000, 1),
                }

                if settings.ready_check_migrations:
                    result = await session.execute(
                        text("SELECT version_num FROM alembic_version")
                    )
                    actual = result.scalar_one_or_none()
                    expected = _expected_head_revision()
                    if actual == expected:
                        checks["migrations"] = {"status": "ok", "version": actual}
                    else:
                        checks["migrations"] = {
                            "status": "fail",
                            "error": f"database at {actual!r}, expected {expected!r}",
                        }
                        healthy = False
                else:
                    checks["migrations"] = {"status": "skipped"}
    except Exception as exc:  # noqa: BLE001 — deliberate: any DB failure -> 503, never 500
        checks.setdefault("database", {"status": "fail", "error": str(exc)})
        checks.setdefault("migrations", {"status": "skipped"})
        healthy = False

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks}
    return {"status": "ready", "checks": checks}


@router.get("/info")
async def info():
    """
    Identity. Spec §3.4 — makes load-balancing, canaries and failover
    visible to the naked eye by showing which specific pod answered.

    node/pod_ip only exist via Kubernetes' Downward API (fieldRef:
    spec.nodeName / status.podIP) — under plain docker-compose neither env
    var is set, so they fall back to "local" / "n/a" rather than raising.
    That fallback is itself informative: it's how you'll tell at a glance
    whether this instance is running under Compose or Kubernetes later.
    """
    return {
        "service": settings.service_name,
        "version": settings.app_version,
        "git_commit": settings.git_commit,
        "build_time": settings.build_time,
        "hostname": _HOSTNAME,
        "node": os.environ.get("NODE_NAME", "local"),
        "pod_ip": os.environ.get("POD_IP", "n/a"),
        "region": settings.region,
        "environment": settings.environment,
        "tier": settings.tier,
    }
