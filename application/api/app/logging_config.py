"""
Structured logging — see spec §4 "Logging".

WHAT: every log line becomes one JSON object on stdout, carrying a
correlation_id that ties together every log line produced while handling
one request. WHO READS IT: humans via `docker logs` / `kubectl logs` today;
Loki from project 02 onward — this file's output format is the contract
that later project's log-correlation exercises depend on, so its shape
should not change casually once other projects start depending on it.

WHY stdout only, no files, no rotation: twelve-factor. The app never
decides where its logs end up — the platform (Docker's log driver,
Kubernetes' container runtime, later Loki's scraper) owns that. A file
handler here would be invisible to `kubectl logs` and silently fill a
container's writable layer.

correlation_id is a ContextVar, not a function argument, so any code
anywhere in a request's call stack can log with the right ID attached
without threading it through every function signature. The middleware
that sets it lives in main.py (Step 3); this module only needs to know
how to *read* it.
"""

import contextvars
import json
import logging
import socket
import sys
import time

from app.config import settings

# Set once per request by the correlation-ID middleware (main.py). Read here
# by the formatter. None outside of a request (e.g. startup logs).
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

_HOSTNAME = socket.gethostname()

# Attributes every stdlib LogRecord already has — anything else passed via
# `logger.info(msg, extra={...})` is a genuine extra field we want to
# surface in the JSON output.
_STANDARD_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime_iso(record),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "service": settings.service_name,
            "version": settings.app_version,
            "correlation_id": correlation_id_var.get(),
            "pod": _HOSTNAME,
        }
        # Surface any extra=dict(...) fields the caller attached, e.g.
        # method/path/status/duration_ms on an access-log line.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and key not in entry:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)

    @staticmethod
    def formatTime_iso(record: logging.LogRecord) -> str:
        return (
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z"
        )


class ConsoleFormatter(logging.Formatter):
    """LOG_FORMAT=console — human-readable, for local development only."""

    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_var.get()
        cid_part = f" [{cid[:8]}]" if cid else ""
        base = f"{record.levelname:<7}{cid_part} {record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging() -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        JSONFormatter() if settings.log_format == "json" else ConsoleFormatter()
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # uvicorn installs its own handlers by default; replace them so every
    # log line — ours and uvicorn's — goes through the same formatter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
