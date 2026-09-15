from __future__ import annotations

from io import StringIO
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.test import override_settings

from ai.models import PulseHeartbeat
from ai.models.core import Instance


@pytest.fixture
def seeded_instance(db):
    return Instance.objects.create(
        id="nibras",
        name="nibras",
        display_name="Nibras",
        host_db_url="postgres://localhost/nibras_dev",
        host_api_url="https://nibras.local",
        status="active",
    )


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_dry_run_creates_no_heartbeat_rows_and_no_loop_calls(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    called = {"value": False}

    def _fail_if_called(self, **kwargs):
        called["value"] = True
        raise AssertionError("loop execution should not run during --dry-run")

    monkeypatch.setattr(Command, "_run_loop", _fail_if_called)

    out = StringIO()
    call_command("run_pulse_maintenance", "--dry-run", stdout=out)

    assert PulseHeartbeat.objects.count() == 0
    assert called["value"] is False


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_real_run_writes_one_terminal_row_per_loop(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    produced = {
        "proactive": 2,
        "consolidation": 3,
        "distill": 4,
        "decay": 5,
    }

    def _fake_run(self, **kwargs):
        return produced[kwargs["loop_name"]]

    monkeypatch.setattr(Command, "_run_loop", _fake_run)

    out = StringIO()
    call_command("run_pulse_maintenance", stdout=out)

    rows = list(PulseHeartbeat.objects.order_by("loop"))
    assert len(rows) == 4
    assert {row.loop for row in rows} == set(produced.keys())
    for row in rows:
        assert row.status == "ok"
        assert row.finished_at is not None
        assert row.items_produced == produced[row.loop]


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_failing_loop_marks_error_and_other_loops_continue(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    def _fake_run(self, **kwargs):
        if kwargs["loop_name"] == "distill":
            raise RuntimeError("distill failure")
        return 1

    monkeypatch.setattr(Command, "_run_loop", _fake_run)

    out = StringIO()
    call_command("run_pulse_maintenance", stdout=out)

    rows = {row.loop: row for row in PulseHeartbeat.objects.all()}
    assert len(rows) == 4
    assert rows["distill"].status == "error"
    assert "distill failure" in rows["distill"].error
    assert rows["proactive"].status == "ok"
    assert rows["consolidation"].status == "ok"
    assert rows["decay"].status == "ok"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_repeat_runs_are_safe_and_terminal(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    def _fake_run(self, **kwargs):
        return 1

    monkeypatch.setattr(Command, "_run_loop", _fake_run)

    out = StringIO()
    call_command("run_pulse_maintenance", stdout=out)
    call_command("run_pulse_maintenance", stdout=out)

    rows = PulseHeartbeat.objects.order_by("created_at")
    assert rows.count() == 8
    assert rows.filter(status="running").count() == 0
    assert rows.filter(finished_at__isnull=True).count() == 0


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_existing_running_heartbeat_is_detected_and_skipped(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    PulseHeartbeat.objects.create(
        instance_id="nibras",
        loop="consolidation",
        started_at=seeded_instance.created_at,
        status="running",
    )

    def _fake_run(self, **kwargs):
        if kwargs["loop_name"] == "consolidation":
            raise AssertionError("consolidation should be skipped when running exists")
        return 1

    monkeypatch.setattr(Command, "_run_loop", _fake_run)

    out = StringIO()
    call_command("run_pulse_maintenance", stdout=out)

    assert PulseHeartbeat.objects.filter(loop="consolidation").count() == 1
    assert PulseHeartbeat.objects.filter(loop="consolidation", status="running").count() == 1


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_budget_exhausted_marks_skipped(monkeypatch, seeded_instance):
    from ai.management.commands.run_pulse_maintenance import Command

    def _fake_usage(self, instance_id):
        return (10, Decimal("5.0"))

    def _fail_if_called(self, **kwargs):
        raise AssertionError("loop execution should be skipped when budget is exhausted")

    monkeypatch.setattr(Command, "_llm_usage_for_day", _fake_usage)
    monkeypatch.setattr(Command, "_run_loop", _fail_if_called)
    monkeypatch.setattr(Command, "_daily_budget_usd", lambda self: Decimal("5.0"))

    out = StringIO()
    call_command("run_pulse_maintenance", stdout=out)

    rows = list(PulseHeartbeat.objects.all())
    assert len(rows) == 4
    assert {row.status for row in rows} == {"skipped"}
