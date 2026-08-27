# File: backend/core/log_filters.py
# EPH-6A / P1-11 — correlation-ID plumbing for structured JSON logs.
#
# RequestLoggingMiddleware stores the request correlation ID in a thread-local
# so every log record emitted while the request is being handled (middleware,
# views, services, ORM callbacks) carries the same ``correlation_id`` field.
# The middleware clears the thread-local when the response is done, so records
# outside request handling fall back to an empty string.

import logging
import threading

_local = threading.local()


def set_correlation_id(correlation_id: str) -> None:
    """Store the current request's correlation ID for this thread."""
    _local.correlation_id = correlation_id or ''


def clear_correlation_id() -> None:
    """Remove the thread-local correlation ID (end of request)."""
    try:
        del _local.correlation_id
    except AttributeError:
        pass


class CorrelationIdFilter(logging.Filter):
    """Injects ``correlation_id`` into every LogRecord passing through.

    Attached to the console and file handlers; records are modified before
    formatting so the JSON formatter never sees a missing attribute.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Prefer an explicit ``extra``-provided value; fall back to thread-local.
        if not getattr(record, 'correlation_id', None):
            record.correlation_id = getattr(_local, 'correlation_id', '')
        return True
