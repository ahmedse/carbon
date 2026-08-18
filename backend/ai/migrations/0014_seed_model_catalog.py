"""Seed the AI model catalog (Phase 20-A).

Data migration — kept separate from the schema migration (data-layer.md rule:
one logical change per migration, data migration separate from schema).

Seeds 8 rows across three tiers (fast / balanced / brain) with cost-faithful
per-1M pricing (single source of truth: this table), context windows, and a
retirement path demonstrated via ``deprecated`` + ``superseded_by``.
"""

from django.db import migrations


# model_id -> (display_name, description, tier, version, context_window,
#              input_cost_per_1m, output_cost_per_1m, capabilities,
#              superseded_by_model_id or None)
CATALOG_ROWS = [
    # ── fast ──────────────────────────────────────────────────────────
    {
        "model_id": "gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "description": "Fastest, most affordable model for routine and high-volume tasks.",
        "tier": "fast",
        "version": "openai/gpt-4o-mini",
        "context_window": 128000,
        "input_cost_per_1m": "0.15",
        "output_cost_per_1m": "0.60",
        "capabilities": ["vision", "function_calling"],
        "superseded_by": None,
    },
    {
        "model_id": "claude-haiku-4.5",
        "display_name": "Claude Haiku 4.5",
        "description": "Low-latency Claude model for quick, structured answers.",
        "tier": "fast",
        "version": "anthropic/claude-haiku-4.5",
        "context_window": 200000,
        "input_cost_per_1m": "1.00",
        "output_cost_per_1m": "5.00",
        "capabilities": ["vision", "function_calling"],
        "superseded_by": None,
    },
    # ── balanced ──────────────────────────────────────────────────────
    {
        "model_id": "claude-sonnet-4.5",
        "display_name": "Claude Sonnet 4.5",
        "description": "Balanced Claude model for analysis and multi-step reasoning.",
        "tier": "balanced",
        "version": "anthropic/claude-sonnet-4.5",
        "context_window": 200000,
        "input_cost_per_1m": "3.00",
        "output_cost_per_1m": "5.00",
        "capabilities": ["vision", "function_calling", "reasoning"],
        "superseded_by": None,
    },
    {
        "model_id": "claude-3-5-sonnet",
        "display_name": "Claude 3.5 Sonnet",
        "description": "Previous-generation Sonnet, retired in favor of Sonnet 4.5.",
        "tier": "balanced",
        "version": "anthropic/claude-3-5-sonnet-latest",
        "context_window": 200000,
        "input_cost_per_1m": "3.00",
        "output_cost_per_1m": "15.00",
        "capabilities": ["vision", "function_calling"],
        "superseded_by": "claude-sonnet-4.5",
    },
    # ── brain ─────────────────────────────────────────────────────────
    {
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "description": "High-reasoning flagship for complex, high-stakes generation.",
        "tier": "brain",
        "version": "openai/gpt-4o",
        "context_window": 128000,
        "input_cost_per_1m": "2.50",
        "output_cost_per_1m": "10.00",
        "capabilities": ["vision", "function_calling", "reasoning"],
        "superseded_by": None,
    },
    {
        "model_id": "claude-opus-4.5",
        "display_name": "Claude Opus 4.5",
        "description": "Claude's most capable model for the hardest reasoning tasks.",
        "tier": "brain",
        "version": "anthropic/claude-opus-4.5",
        "context_window": 200000,
        "input_cost_per_1m": "15.00",
        "output_cost_per_1m": "75.00",
        "capabilities": ["vision", "function_calling", "reasoning"],
        "superseded_by": None,
    },
    # ── retired versions (demonstrate version + retirement path) ──────
    {
        "model_id": "claude-haiku-3.5",
        "display_name": "Claude Haiku 3.5",
        "description": "Prior Haiku release, superseded by Haiku 4.5.",
        "tier": "fast",
        "version": "anthropic/claude-haiku-3.5",
        "context_window": 200000,
        "input_cost_per_1m": "0.80",
        "output_cost_per_1m": "4.00",
        "capabilities": ["vision", "function_calling"],
        "superseded_by": "claude-haiku-4.5",
    },
    {
        "model_id": "gpt-4o-2024-05-13",
        "display_name": "GPT-4o (May 2024)",
        "description": "Original GPT-4o snapshot, superseded by the current GPT-4o.",
        "tier": "brain",
        "version": "openai/gpt-4o-2024-05-13",
        "context_window": 128000,
        "input_cost_per_1m": "5.00",
        "output_cost_per_1m": "15.00",
        "capabilities": ["vision", "function_calling"],
        "superseded_by": "gpt-4o",
    },
]


def seed_catalog(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    # First pass: create/update active rows so self-FK targets exist.
    for row in CATALOG_ROWS:
        if row["superseded_by"]:
            continue
        ModelCatalog.objects.update_or_create(
            model_id=row["model_id"],
            defaults={
                "display_name": row["display_name"],
                "description": row["description"],
                "tier": row["tier"],
                "version": row["version"],
                "context_window": row["context_window"],
                "input_cost_per_1m": row["input_cost_per_1m"],
                "output_cost_per_1m": row["output_cost_per_1m"],
                "capabilities": row["capabilities"],
                "deprecated": False,
                "superseded_by": None,
            },
        )
    # Second pass: deprecated rows referencing their replacement.
    for row in CATALOG_ROWS:
        if not row["superseded_by"]:
            continue
        replacement = ModelCatalog.objects.filter(
            model_id=row["superseded_by"]
        ).first()
        ModelCatalog.objects.update_or_create(
            model_id=row["model_id"],
            defaults={
                "display_name": row["display_name"],
                "description": row["description"],
                "tier": row["tier"],
                "version": row["version"],
                "context_window": row["context_window"],
                "input_cost_per_1m": row["input_cost_per_1m"],
                "output_cost_per_1m": row["output_cost_per_1m"],
                "capabilities": row["capabilities"],
                "deprecated": True,
                "superseded_by": replacement,
            },
        )


def unseed_catalog(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    ModelCatalog.objects.filter(
        model_id__in=[row["model_id"] for row in CATALOG_ROWS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0013_modelcatalog"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, unseed_catalog),
    ]
