"""Shared, lenient Redis client for engine ephemeral memory (Pulse 0.2 Phase A1).

Redis is the source of truth for short-term and working memory. The client is
created lazily and is never fatal: if Redis is unreachable, ``get_redis_client``
logs a visible warning and returns ``None`` so callers fall back to their
in-process stores (never silently).

This module is pure engine plumbing — it imports nothing from Carbon's domain
apps (RULE_20 / RULE_6).
"""
from __future__ import annotations

import logging
import time

import redis

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.memory.redis")

# Re-check Redis no more than once every N seconds while it is down, so a
# transient outage doesn't spam the log and a permanent one doesn't stall
# every operation with a connection attempt.
_RETRY_COOLDOWN_SECONDS = 5.0

_client: redis.Redis | None = None
_client_unavailable_until: float = 0.0


def get_redis_client() -> redis.Redis | None:
    """Return a connected Redis client, or ``None`` if Redis is unreachable.

    Lazy + lenient: the first call pings Redis. Failures log a warning and
    return ``None``. A short cooldown avoids re-pinging on every subsequent
    call while Redis is down, and allows recovery once it returns.
    """
    global _client, _client_unavailable_until

    if _client is not None:
        return _client

    now = time.monotonic()
    if now < _client_unavailable_until:
        return None

    url = get_settings().PULSE_MEMORY_REDIS_URL
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
    except Exception as exc:  # noqa: BLE001 — connection/socket/OS errors
        _client_unavailable_until = now + _RETRY_COOLDOWN_SECONDS
        logger.warning(
            "Redis unavailable at %s — ephemeral memory falling back to "
            "in-process store (not shared across workers/restarts): %s",
            url,
            exc,
        )
        return None

    _client = client
    return client


def memory_key(prefix: str, conversation_id: str) -> str:
    """Build the namespaced Redis key for a conversation.

    Scheme: ``pulse:{prefix}:{instance}:{conversation}`` (e.g.
    ``pulse:st:default:conv-123``).
    """
    instance = get_settings().PULSE_INSTANCE_ID
    return f"pulse:{prefix}:{instance}:{conversation_id}"
