"""Centralized UTC clock. Returns timezone-aware UTC datetimes.

The engine now persists via the Django ORM (``USE_TZ=True``), which requires
timezone-aware datetimes.  The retired SQLite path stored tz-naive values, so
``utcnow`` previously stripped ``tzinfo``; that is no longer correct and only
produces ``DateTimeField ... received a naive datetime`` warnings.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp (drop-in for the deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)
