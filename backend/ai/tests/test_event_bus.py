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
        received: list[dict] = []

        async def _consume() -> None:
            async for frame in event_bus.subscribe(channel):
                received.append(frame)
                break

        task = asyncio.create_task(_consume())
        # Let the subscription register on the server before publishing.
        await asyncio.sleep(0.5)
        await event_bus.publish(channel, payload)
        await asyncio.wait_for(task, timeout=5.0)

        assert len(received) == 1
        frame = received[0]
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
        received: list[dict] = []

        async def _consume() -> None:
            async for frame in event_bus.subscribe(channel):
                received.append(frame)
                break

        task = asyncio.create_task(_consume())
        await asyncio.sleep(0.5)
        await notifier.broadcast_run_event(
            "test-instance", "run.started", {"run_id": "r-1"}
        )
        await asyncio.wait_for(task, timeout=5.0)

        assert len(received) == 1
        assert received[0]["event_type"] == "run.started"
        assert received[0]["instance_id"] == "test-instance"
        assert received[0]["payload"]["payload"] == {"run_id": "r-1"}

    asyncio.run(_run())
