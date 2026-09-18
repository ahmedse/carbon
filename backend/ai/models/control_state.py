"""Pulse Control Plane durable state (ADR-0036).

One row per instance holding graduated containment + optional budget override.
"""

from __future__ import annotations

from django.db import models

from .base import generate_uuid

CONTAINMENT_NORMAL = "normal"
CONTAINMENT_AUTONOMY_CLAMP = "autonomy_clamp"
CONTAINMENT_TOOL_FREEZE = "tool_freeze"
CONTAINMENT_LEARNING_FREEZE = "learning_freeze"
CONTAINMENT_FULL_STOP = "full_stop"

CONTAINMENT_LEVELS = frozenset(
    {
        CONTAINMENT_NORMAL,
        CONTAINMENT_AUTONOMY_CLAMP,
        CONTAINMENT_TOOL_FREEZE,
        CONTAINMENT_LEARNING_FREEZE,
        CONTAINMENT_FULL_STOP,
    }
)


class PulseControlState(models.Model):
    """Singleton-per-instance control-plane knobs."""

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.CharField(max_length=64, unique=True, db_index=True)
    containment_level = models.CharField(
        max_length=32, default=CONTAINMENT_NORMAL, db_index=True
    )
    autonomy_ceiling = models.CharField(max_length=32, blank=True, default="")
    learning_admissions_frozen = models.BooleanField(default=False)
    daily_budget_usd = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        app_label = "ai"

    def as_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "containment_level": self.containment_level,
            "autonomy_ceiling": self.autonomy_ceiling or None,
            "learning_admissions_frozen": self.learning_admissions_frozen,
            "daily_budget_usd": self.daily_budget_usd,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by or None,
        }


def get_or_create_control_state(instance_id: str) -> PulseControlState:
    obj, _ = PulseControlState.objects.get_or_create(
        instance_id=instance_id,
        defaults={"containment_level": CONTAINMENT_NORMAL},
    )
    return obj
