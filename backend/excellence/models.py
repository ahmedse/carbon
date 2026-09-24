"""Ledger rows (ADR-0051 §5–§6). Append-only events; levels are never stored
except as dated snapshots for trends.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Result(models.TextChoices):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class EvidenceClass(models.TextChoices):
    CONFIGURED = "configured"
    EXECUTED = "executed"
    ENFORCEMENT_VERIFIED = "enforcement-verified"
    FAULT_DEMONSTRATED = "fault-demonstrated"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class Event(models.Model):
    """One check result for one subject on one commit. Never updated."""

    check_id = models.CharField(max_length=80, db_index=True)
    subject_id = models.CharField(max_length=160, db_index=True)
    tier = models.CharField(max_length=40, db_index=True)
    track = models.CharField(max_length=40, blank=True, default="")
    commit = models.CharField(max_length=40, db_index=True)
    result = models.CharField(max_length=12, choices=Result.choices)
    evidence_class = models.CharField(max_length=24, choices=EvidenceClass.choices)
    source = models.TextField(blank=True, default="")
    runner = models.CharField(max_length=40, default="local")
    duration_ms = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [models.Index(fields=["subject_id", "check_id", "-at"])]

    def __str__(self) -> str:
        return f"{self.subject_id} · {self.check_id} · {self.result} @ {self.commit[:7]}"


class Snapshot(models.Model):
    """Derived level frozen on a date, for trends and the ratchet gate."""

    date = models.DateField(db_index=True)
    tier = models.CharField(max_length=40, db_index=True)
    track = models.CharField(max_length=40, blank=True, default="")
    subject_id = models.CharField(max_length=160, db_index=True)
    commit = models.CharField(max_length=40)
    level = models.PositiveSmallIntegerField()
    dimensions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["date", "subject_id"], name="excellence_snapshot_day_subject"),
        ]


class Exemption(models.Model):
    """A check that does not apply to a subject, for a stated reason, until a date."""

    check_id = models.CharField(max_length=80, db_index=True)
    subject_id = models.CharField(max_length=160, db_index=True)
    reason = models.TextField()
    granted_by = models.CharField(max_length=120)
    until = models.DateField(db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["until"]

    def is_active(self, on=None) -> bool:
        on = on or timezone.localdate()
        return self.until >= on


class RunStatus(models.TextChoices):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Run(models.Model):
    """One staff-triggered collector invocation (ADR-0051 P2). Append-only."""

    collectors = models.JSONField(default=list)
    tier = models.CharField(max_length=40, blank=True, default="")
    track = models.CharField(max_length=40, blank=True, default="")
    run_apps = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=RunStatus.choices, default=RunStatus.RUNNING)
    requested_by = models.CharField(max_length=120)
    commit = models.CharField(max_length=40, blank=True, default="")
    event_count = models.PositiveIntegerField(default=0)
    detail = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        return f"Run #{self.pk} {self.status} · {','.join(self.collectors or [])}"


class Initiative(models.Model):
    """A dated goal on top of the ladder: reach a level for a set of apps."""

    title = models.CharField(max_length=160)
    tier = models.CharField(max_length=40, db_index=True)
    target_level = models.PositiveSmallIntegerField()
    app_ids = models.JSONField(default=list, blank=True)
    deadline = models.DateField(db_index=True)
    owner = models.CharField(max_length=120)
    status = models.CharField(max_length=12, default="open")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["deadline", "-id"]
