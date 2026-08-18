"""Model catalog — the single source of truth for selectable AI models.

Phase 20-A. Replaces the thin ``_CHAT_MODEL_CATALOG`` tuple in
``ai/engine/llm/router.py`` as the durable, versioned, cost-faithful catalog
behind the ``GET /ai/models/`` endpoint.

Design intent:

* ``model_id`` is a STABLE slug (never changes across version bumps) so that
  historical usage attribution (Phase 21) can always resolve a model.
* ``tier`` partitions models into user-facing buckets (fast / balanced /
  brain) so the selector can communicate "cheap/fast vs smart/expensive".
* Costs live HERE and nowhere else — the router must read cost from the
  catalog, never recompute ad hoc (Phase 21 depends on this).
* ``deprecated`` + ``superseded_by`` provide a retirement path without
  breaking historical attribution. Deprecated rows are still returned by the
  endpoint.
"""

from decimal import Decimal

from django.db import models


class ModelCatalog(models.Model):
    """A selectable AI model with tier, version, cost, and retirement info."""

    TIER_CHOICES = [
        ("fast", "Fast"),
        ("balanced", "Balanced"),
        ("brain", "Brain"),
    ]

    model_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="Stable slug. Never changes across version bumps — historical "
                  "usage attribution resolves against this id.",
    )
    display_name = models.CharField(max_length=128)
    description = models.TextField(
        blank=True,
        default="",
        help_text="User-facing one-liner shown in the model picker.",
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default="balanced",
        help_text="User-facing bucket: fast (cheap) / balanced / brain (smart, expensive).",
    )
    version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Concrete provider version (server-side only; never exposed as raw routing).",
    )
    context_window = models.PositiveIntegerField(
        default=128000,
        help_text="Maximum context window in tokens.",
    )
    input_cost_per_1m = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0"),
        help_text="USD cost per 1M input tokens (single source of truth for pricing).",
    )
    output_cost_per_1m = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0"),
        help_text="USD cost per 1M output tokens (single source of truth for pricing).",
    )
    deprecated = models.BooleanField(
        default=False,
        help_text="Retired models stay in the catalog for attribution but are "
                  "hidden from new selection in the UI.",
    )
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="supersedes",
        help_text="Replacement model (retirement path).",
    )
    capabilities = models.JSONField(
        default=list,
        blank=True,
        help_text="User-facing capability flags (e.g. vision, function_calling). "
                  "Never raw provider routing.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["deprecated", "input_cost_per_1m", "model_id"]
        indexes = [
            models.Index(fields=["tier", "deprecated"], name="ai_mcat_tier_dep_idx"),
        ]
        verbose_name = "Model Catalog"
        verbose_name_plural = "Model Catalog"

    def __str__(self):
        flag = " (deprecated)" if self.deprecated else ""
        return f"{self.display_name} [{self.tier}]{flag}"
