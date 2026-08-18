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
from typing import Iterable

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

    # ── Phase 21-A: cost + attribution resolution ────────────────────────
    # The catalog is the single source of truth for pricing.  Cost is read
    # from here, never recomputed ad hoc from the router's LLM_COST_MODELS
    # JSON.  ``resolve_model_id`` maps a concrete provider model string
    # (e.g. "anthropic/claude-haiku-4.5") to its stable catalog slug.

    @classmethod
    def resolve_model_id(cls, model: str | None) -> str:
        """Map a concrete provider model string → stable ``model_id`` slug.

        Matches ``model_id`` or ``version`` case-insensitively, then falls
        back to the trailing slug (the part after the last ``/``).  Unknown
        models are returned verbatim so attribution never loses the raw id.
        """
        if not model:
            return ""
        key = (model or "").strip()
        if not key:
            return ""
        row = cls.objects.filter(
            models.Q(model_id__iexact=key) | models.Q(version__iexact=key)
        ).first()
        if row is not None:
            return row.model_id
        slug = key.rsplit("/", 1)[-1]
        row = cls.objects.filter(model_id__iexact=slug).first()
        if row is not None:
            return row.model_id
        return key

    @classmethod
    def compute_cost(
        cls,
        model_id: str | None,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Decimal:
        """Compute USD cost from catalog input/output rates.

        Returns ``Decimal("0.0")`` when the model is unknown.  This is the
        ONLY cost computation path for persisted usage.
        """
        if not model_id:
            return Decimal("0.0")
        row = cls.objects.filter(model_id__iexact=model_id).first()
        if row is None:
            return Decimal("0.0")
        in_cost = (Decimal(int(prompt_tokens or 0)) / Decimal("1000000")) * row.input_cost_per_1m
        out_cost = (Decimal(int(completion_tokens or 0)) / Decimal("1000000")) * row.output_cost_per_1m
        return (in_cost + out_cost).quantize(Decimal("0.000001"))

    @classmethod
    def resolve_tier(cls, model_id: str | None) -> str:
        """Return the catalog tier for a model slug, or ``"unknown"``."""
        if not model_id:
            return "unknown"
        row = cls.objects.filter(model_id__iexact=model_id).first()
        return row.tier if row is not None else "unknown"

    @classmethod
    def tier_map(cls, model_ids: Iterable[str | None]) -> dict[str, str]:
        """Resolve tiers for many slugs in ONE query.

        The batch counterpart to :meth:`resolve_tier` — usage aggregation
        (``AIUsage.summary``) buckets per model, and calling ``resolve_tier``
        per row is an N+1.  Returns ``{model_id: tier}`` for known slugs;
        unknown/empty ids are omitted (callers default to ``"unknown"``).
        """
        ids = {m for m in model_ids if m}
        if not ids:
            return {}
        return dict(
            cls.objects.filter(model_id__in=ids).values_list("model_id", "tier")
        )
