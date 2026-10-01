"""Per-deployment Pulse app enablement (Platform → Pulse tab)."""

from __future__ import annotations

from django.db import models

from .base import generate_uuid


class PulseAppEnablement(models.Model):
    """Steward toggle: Pulse may use this app's catalog rows on this pack.

    Missing row means default on for a preset app the pack owns.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)
    instance_id = models.CharField(max_length=64, db_index=True)
    app_slug = models.CharField(max_length=64)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        app_label = "ai"
        unique_together = (("instance_id", "app_slug"),)

    def as_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "app_slug": self.app_slug,
            "enabled": self.enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by or None,
        }
