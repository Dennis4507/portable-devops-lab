"""
The standard operational contract every project in this lab depends on.
See docs/projects/00-reference-app/spec.md §3.

This file currently implements only /health and /info — the two endpoints
that need no database. /ready, /metrics, /work and /error-test follow once
the database layer exists (next build step).
"""

import os
import socket
import time

from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter()

_HOSTNAME = os.environ.get("HOSTNAME") or socket.gethostname()


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
