"""Redis pub/sub event bus for engine events (Pulse 0.2 Phase A2).

Redis is transport only — transient, fire-and-forget pub/sub (RULE_6). Nothing
is persisted to Redis beyond the in-flight message, and no Postgres rows are
touched here. A ``publish`` writes a JSON frame to the channel
``pulse:events:{instance}``; a ``subscribe`` yields those frames back as
decoded dicts.

The bus is async-native (``redis.asyncio``) so it can be awaited from the
existing async callers in ``notifier.py`` / ``delivery.py`` without blocking
the event loop.

Lenient by design (mirrors ``memory/_redis.py``): if Redis is unreachable,
``publish`` logs a warning and no-ops, and ``subscribe`` yields nothing. The
bus never crashes a caller.

This module is pure engine plumbing — it imports nothing from Carbon's domain
apps (RULE_20 / RULE_6).
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis import asyncio as aioredis

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.events.bus")

# Fail fast rather than hang the event loop when Redis is unreachable.
_CONNECT_TIMEOUT_SECONDS = 2.0
_SOCKET_TIMEOUT_SECONDS = 2.0


def events_channel() -> str:
    """Return the pub/sub channel for this instance's engine events.

    Scheme: ``pulse:events:{instance}`` where the instance id comes from
    ``get_settings().PULSE_INSTANCE_ID``.
    """
    instance = get_settings().PULSE_INSTANCE_ID
    return f"pulse:events:{instance}"


def build_event_frame(event_type: str, instance_id: str, payload: dict) -> dict:
    """Build the JSON frame published on the bus.

    The shape is kept stable so later phases (A3 SSE delivery) can consume it
    without coupling to call-site internals.
    """
    return {
        "event_type": event_type,
        "instance_id": instance_id,
        "payload": payload,
    }


def _make_client() -> aioredis.Redis:
    """Create a fresh async Redis client for a single pub/sub operation."""
    url = get_settings().PULSE_MEMORY_REDIS_URL
    return aioredis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=_SOCKET_TIMEOUT_SECONDS,
    )


async def _aclose(obj: Any) -> None:
    """Best-effort async close (handles Redis and PubSub alike)."""
    closer = getattr(obj, "aclose", None) or getattr(obj, "close", None)
    if closer is None:
        return
    try:
        await closer()
    except Exception:  # noqa: BLE001 — never raise during cleanup
        pass


async def publish(channel: str, payload: dict) -> None:
    """Publish ``payload`` (JSON-encoded) to ``channel``. Never raises.

    If Redis is unreachable this logs a warning and drops the event — the bus
    is a transient best-effort transport, not a durability boundary.
    """
    client = _make_client()
    try:
        await client.publish(channel, json.dumps(payload, default=str))
    except Exception as exc:  # noqa: BLE001 — connection/socket/OS errors
        logger.warning(
            "Redis publish failed on %s (transport-only — dropping event): %s",
            channel,
            exc,
        )
    finally:
        await _aclose(client)


async def subscribe(channel: str) -> AsyncIterator[dict]:
    """Yield decoded JSON frames from ``channel``.

    If Redis is unreachable (or the connection drops), the generator simply
    ends without yielding anything — it never raises to the caller.
    """
    client = _make_client()
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                yield json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Dropping non-JSON bus frame on %s", channel)
                continue
    except Exception as exc:  # noqa: BLE001 — lenient: yield nothing
        logger.warning("Redis subscribe ended for %s: %s", channel, exc)
    finally:
        await _aclose(pubsub)
        await _aclose(client)
