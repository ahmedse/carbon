"""Centralized UTC clock. Returns naive-UTC datetimes to match existing
SQLite-stored (tz-naive) values — avoids naive/aware comparison errors."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (drop-in for the deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
