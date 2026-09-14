"""Tests for the Redis pub/sub event bus (Pulse 0.2 Phase A2).

Round-trip tests use the real Redis instance at 127.0.0.1:6379 — the bus is
transient transport only (no durable state, no Postgres). The resilience tests
point the client at a closed port and assert the bus degrades gracefully
(publish no-ops, subscribe yields nothing) instead of raising.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from ai.engine.core import event_bus
from ai.engine.core.config import get_settings


def _unique_payload() -> dict:
    return {
        "event_type": "test.event",
        "instance_id": "test",
        "payload": {"token": uuid.uuid4().hex},
    }


def test_publish_subscribe_round_trip():
    """A published JSON frame round-trips back through a subscriber."""

    async def _run() -> None:
        channel = event_bus.events_channel()
        payload = _unique_payload()
        token = payload["payload"]["token"]
        received: list[dict] = []
        ready = asyncio.Event()

        async def _consume() -> None:
            async for frame in event_bus.subscribe(channel, ready=ready):
                received.append(frame)
                if (frame.get("payload") or {}).get("token") == token:
                    break

        task = asyncio.create_task(_consume())
        # Deterministic: await subscription readiness instead of a fixed sleep,
        # so publish cannot race subscribe. Stale frames from other publishers
        # (shared channel) are ignored by filtering on our unique token.
        await asyncio.wait_for(ready.wait(), timeout=5.0)
        await event_bus.publish(channel, payload)
        await asyncio.wait_for(task, timeout=5.0)

        own = [
            f for f in received if (f.get("payload") or {}).get("token") == token
        ]
        assert len(own) == 1
        frame = own[0]
        assert frame["event_type"] == payload["event_type"]
        assert frame["instance_id"] == payload["instance_id"]
        assert frame["payload"] == payload["payload"]

    asyncio.run(_run())


def test_publish_does_not_raise_when_redis_down(monkeypatch):
    """publish is lenient: it logs a warning and no-ops when Redis is unreachable."""
    settings = get_settings()
    monkeypatch.setattr(
        settings, "PULSE_MEMORY_REDIS_URL", "redis://127.0.0.1:6399/0"
    )

    async def _run() -> None:
        await event_bus.publish(event_bus.events_channel(), _unique_payload())

    # Must not raise.
    asyncio.run(_run())


def test_subscribe_yields_nothing_when_redis_down(monkeypatch):
    """subscribe yields nothing (never raises) when Redis is unreachable."""
    settings = get_settings()
    monkeypatch.setattr(
        settings, "PULSE_MEMORY_REDIS_URL", "redis://127.0.0.1:6399/0"
    )

    async def _run() -> None:
        frames: list[dict] = []
        async for frame in event_bus.subscribe(event_bus.events_channel()):
            frames.append(frame)
        assert frames == []

    asyncio.run(_run())


def test_notifier_broadcast_run_event_publishes_to_bus():
    """notifier.broadcast_run_event publishes a run-event frame to the bus."""
    from ai.engine.cognition import notifier

    async def _run() -> None:
        channel = event_bus.events_channel()
        # Unique run_id so we can pick OUR frame out of the shared channel —
        # other tests (and a live dev server) publish run events to the same
        # `pulse:events:{instance}` pub/sub channel, so a stale frame may arrive
        # before ours. Consume until our own frame is seen.
        run_id = f"r-{uuid.uuid4().hex}"
        received: list[dict] = []
        ready = asyncio.Event()

        async def _consume() -> None:
            async for frame in event_bus.subscribe(channel, ready=ready):
                received.append(frame)
                payload = frame.get("payload") or {}
                if payload.get("payload", {}).get("run_id") == run_id:
                    break

        task = asyncio.create_task(_consume())
        # Deterministic: await subscription readiness before publishing.
        await asyncio.wait_for(ready.wait(), timeout=5.0)
        await notifier.broadcast_run_event(
            "test-instance", "run.started", {"run_id": run_id}
        )
        await asyncio.wait_for(task, timeout=5.0)

        own = [
            f
            for f in received
            if (f.get("payload") or {}).get("payload", {}).get("run_id") == run_id
        ]
        assert len(own) == 1
        assert own[0]["event_type"] == "run.started"
        assert own[0]["instance_id"] == "test-instance"
        assert own[0]["payload"]["payload"] == {"run_id": run_id}

    asyncio.run(_run())
