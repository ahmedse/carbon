"""Healthy Foods Factory domain models (DESIGN-PLATFORM.md §8.4).

Three artifacts back the whole healthy domain:

* ``ERPSnapshot``   — audit record of one read-only extract from the legacy
                      Healthy ERP (Azure PostgreSQL). Every pipeline run is
                      anchored by a snapshot so provenance is never lost.
* ``LoadoutSheet``  — weekly per-rep van-load recommendation (pipeline 1
                      output: "returns / load-out demand").
* ``RepHealthCard`` — weekly per-rep health metrics (pipeline 2 output:
                      churn / retention / coverage / AR).
"""
import uuid

from django.conf import settings
from django.db import models


class ERPSnapshot(models.Model):
    """Read-only ERP extract audit record.

    The extract is issued behind the ``connections.DataSource`` seam and is
    strictly read-only — the Healthy app NEVER writes to the legacy ERP.
    """

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_view = models.CharField(max_length=200)
    extract_params = models.JSONField(default=dict, blank=True)
    row_count = models.BigIntegerField(null=True, blank=True)
    dataset_version_id = models.UUIDField(null=True, blank=True)
    data_source = models.ForeignKey(
        'connections.DataSource',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='erp_snapshots',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    error_detail = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='healthy_erp_snapshots',
    )

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.source_view} ({self.status})"


class LoadoutSheet(models.Model):
    """Weekly per-rep van-load plan (pipeline 1: returns / load-out demand)."""

    week_start = models.DateField()
    rep_code = models.CharField(max_length=64)
    rep_name = models.CharField(max_length=200, blank=True)
    prediction_ref = models.UUIDField(null=True, blank=True)
    # List of {item_code, item_name, qty_recommended, qty_actual, ...} rows.
    line_items = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='healthy_loadout_sheets',
    )

    class Meta:
        ordering = ['-week_start', 'rep_code']
        unique_together = ('week_start', 'rep_code')

    def __str__(self):
        return f"{self.rep_code} load-out — {self.week_start}"


class RepHealthCard(models.Model):
    """Weekly per-rep health card (pipeline 2: churn / retention / coverage)."""

    week_start = models.DateField()
    rep_code = models.CharField(max_length=64)
    churn_probability = models.FloatField(null=True, blank=True)
    active_customer_count = models.IntegerField(null=True, blank=True)
    visit_coverage = models.FloatField(null=True, blank=True)
    avg_order_value = models.FloatField(null=True, blank=True)
    ar_overdue_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    prediction_ref = models.UUIDField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start', 'rep_code']
        unique_together = ('week_start', 'rep_code')

    def __str__(self):
        return f"{self.rep_code} health — {self.week_start}"
