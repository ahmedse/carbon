"""Host-owned heartbeat telemetry for Pulse maintenance loops.

Durable state lives in ``ai.models`` (RULE_6). Each row tracks one loop run
for one instance and is closed to a terminal status (ok/error/skipped).
"""

import uuid

from django.db import models

from .base import AppScopeMixin


class PulseHeartbeat(AppScopeMixin):
    """Durable telemetry for on-demand Pulse maintenance loops."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance_id = models.TextField(db_index=True)
    loop = models.CharField(max_length=32, db_index=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, db_index=True)
    items_produced = models.IntegerField(default=0)
    llm_calls = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "ai"
