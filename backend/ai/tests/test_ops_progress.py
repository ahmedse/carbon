"""Tests for the AI operations-progress capability (Pulse 0.2 Wave D1).

Round-trip tests use the real Redis bus (transient transport). The scoping
tests exercise the pure ``_op_frame_visible`` filter with a lightweight fake
user — no database access — so they run fast and stay deterministic.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from ai import ops_progress


def _fake_user(pk=42, is_superuser=False):
    return SimpleNamespace(id=pk, is_superuser=is_superuser)


def test_build_op_progress_payload_is_outcome_shaped():
    """The payload carries outcome copy and no engine jargon (RULE_23)."""
    payload = ops_progress.build_op_progress_payload(
        "dq_run",
        17,
        "running",
        "Checking 3 quality rules…",
        percent=45,
        host_user_id=42,
    )

    assert payload["op_type"] == "dq_run"
    assert payload["op_id"] == "17"
    assert payload["status"] == "running"
    assert payload["message"] == "Checking 3 quality rules…"
    assert payload["percent"] == 45
    assert payload["host_user_id"] == "42"
    assert payload["visibility"] == "private"
    assert payload["app_identifier"] == "carbon"
    assert "created_at" in payload

    # RULE_23: no engine jargon ever crosses the surface.
    forbidden = {
        "pulse_task_id", "channel", "handler", "trigger_id",
        "condition_json", "delivery_channel", "job_type", "spec",
    }
    assert not (set(payload) & forbidden)


def test_publish_op_progress_round_trips():
    """An ``op.progress`` frame round-trips through the real bus."""

    async def _run() -> None:
        received: list[dict] = []

        async def _consume() -> None:
            async for frame in ops_progress.subscribe(ops_progress.events_channel()):
                if frame.get("event_type") == ops_progress.EVENT_TYPE:
                    received.append(frame)
                    break

        task = asyncio.create_task(_consume())
        await asyncio.sleep(0.5)
        await ops_progress.publish_op_progress(
            "report", 9, "done", "Report ready.", percent=100, host_user_id=7
        )
        await asyncio.wait_for(task, timeout=5.0)

        assert len(received) == 1
        frame = received[0]
        assert frame["event_type"] == "op.progress"
        assert frame["payload"]["op_id"] == "9"
        assert frame["payload"]["status"] == "done"

    asyncio.run(_run())


def test_publish_op_progress_sync_fire_and_forget():
    """The sync wrapper delivers a frame without blocking the caller."""
    received: list[dict] = []

    async def _consume() -> None:
        async for frame in ops_progress.subscribe(ops_progress.events_channel()):
            if frame.get("event_type") == ops_progress.EVENT_TYPE:
                received.append(frame)
                return

    # Subscribe in a background thread so the sync publisher is exercised in
    # the main (sync) flow.
    import threading

    t = threading.Thread(
        target=lambda: asyncio.run(_consume()), daemon=True
    )
    t.start()
    time.sleep(0.5)

    ops_progress.publish_op_progress_sync(
        "import", 3, "running", "Writing 1,200 records…", percent=60, host_user_id=1
    )

    deadline = time.time() + 5.0
    while not received and time.time() < deadline:
        time.sleep(0.1)
    assert received, "sync publisher did not deliver a frame"
    assert received[0]["payload"]["op_id"] == "3"


def test_op_frame_visible_private_to_owner(monkeypatch):
    """A user sees only their own op-progress frames."""
    from accounts import rbac_utils

    monkeypatch.setattr(rbac_utils, "user_is_global_admin", lambda u: False)

    payload = ops_progress.build_op_progress_payload(
        "dq_run", 1, "running", "Checking…", host_user_id=42
    )
    assert ops_progress._op_frame_visible(_fake_user(42), payload) is True
    assert ops_progress._op_frame_visible(_fake_user(99), payload) is False


def test_op_frame_visible_superuser_and_wrong_app(monkeypatch):
    """Superusers see all; frames from another platform are dropped."""
    from accounts import rbac_utils

    monkeypatch.setattr(rbac_utils, "user_is_global_admin", lambda u: False)

    payload = ops_progress.build_op_progress_payload(
        "dq_run", 1, "running", "Checking…", host_user_id=42
    )
    assert ops_progress._op_frame_visible(_fake_user(99, is_superuser=True), payload) is True

    other_app = dict(payload, app_identifier="nibras")
    assert ops_progress._op_frame_visible(_fake_user(42), other_app) is False


def test_stream_view_requires_authentication():
    """The SSE endpoint is authenticated."""
    assert ops_progress.OperationsStreamView.permission_classes
    from rest_framework.permissions import IsAuthenticated

    assert IsAuthenticated in ops_progress.OperationsStreamView.permission_classes


def test_register_progress_refresher_dedupes_and_runs(monkeypatch):
    """Refreshers register once and are all invoked by ``_refresh_for_user``."""
    monkeypatch.setattr(ops_progress, "_REFRESHERS", [])
    calls: list[int] = []

    def one(user):
        calls.append(1)

    def two(user):
        calls.append(2)

    ops_progress.register_progress_refresher(one)
    ops_progress.register_progress_refresher(one)  # deduped
    ops_progress.register_progress_refresher(two)

    assert ops_progress._REFRESHERS == [one, two]
    ops_progress._refresh_for_user(_fake_user(42))
    assert calls == [1, 2]


def test_refresh_for_user_swallows_errors(monkeypatch):
    """A raising refresher never breaks the stream loop that calls it."""
    monkeypatch.setattr(ops_progress, "_REFRESHERS", [])

    def bad(user):
        raise RuntimeError("boom")

    good = []
    ops_progress.register_progress_refresher(bad)
    ops_progress.register_progress_refresher(lambda u: good.append(u.id))

    # Must not raise, and the healthy refresher still runs.
    ops_progress._refresh_for_user(_fake_user(7))
    assert good == [7]
