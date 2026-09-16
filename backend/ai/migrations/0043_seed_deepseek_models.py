"""Seed DeepSeek models into ModelCatalog (picker + cost attribution).

Pricing source: https://api-docs.deepseek.com/quick_start/pricing (checked 2026-09-16).

DeepSeek bills peak vs off-peak (peak = 2×). Peak windows are Mon–Fri
01:00–04:00 and 06:00–10:00 UTC; all other hours (incl. weekends) are off-peak.

Catalog stores **peak cache-miss** input + **peak** output so usage/budget
never under-estimates. Descriptions call out the 2× peak and that Flash remains
far cheaper than Claude Sonnet even at peak.
"""

from django.db import migrations

# Official rates (USD / 1M tokens), 2026-09 V4.1 schedule:
#   deepseek-flash:  miss $0.15/$0.30 off/peak · out $0.60/$1.20
#   deepseek-v4-pro: miss $0.66/$1.32 off/peak · out $1.98/$3.96
# Claude Sonnet 4.5/4.6 for comparison: $3.00 in / $15.00 out (flat).
DEEPSEEK_ROWS = [
    {
        "model_id": "deepseek-flash",
        "display_name": "DeepSeek Flash",
        "description": (
            "DeepSeek-V4.1-Flash — cheapest default. Catalog rates are PEAK "
            "(Mon–Fri 01–04 & 06–10 UTC = 2×); off-peak is half. Even at peak "
            "(~$0.30/$1.20 per 1M) still ~10× cheaper than Claude Sonnet ($3/$15)."
        ),
        "tier": "fast",
        "version": "deepseek/deepseek-flash",
        "context_window": 1_000_000,
        "input_cost_per_1m": "0.3000",   # peak cache-miss
        "output_cost_per_1m": "1.2000",  # peak
        "capabilities": ["vision", "function_calling", "reasoning", "thinking"],
        "superseded_by": None,
        "deprecated": False,
    },
    {
        "model_id": "deepseek-v4-pro",
        "display_name": "DeepSeek V4 Pro",
        "description": (
            "DeepSeek-V4-Pro — stronger reasoning. Catalog rates are PEAK "
            "(Mon–Fri 01–04 & 06–10 UTC = 2×); off-peak is half. Peak "
            "(~$1.32/$3.96 per 1M) still under Claude Sonnet ($3/$15)."
        ),
        "tier": "brain",
        "version": "deepseek/deepseek-v4-pro",
        "context_window": 1_000_000,
        "input_cost_per_1m": "1.3200",
        "output_cost_per_1m": "3.9600",
        "capabilities": ["function_calling", "reasoning", "thinking"],
        "superseded_by": None,
        "deprecated": False,
    },
    # Legacy API aliases still accepted by DeepSeek; keep for attribution.
    {
        "model_id": "deepseek-chat",
        "display_name": "DeepSeek Chat (legacy)",
        "description": "Legacy alias — routed to DeepSeek Flash; use deepseek-flash.",
        "tier": "fast",
        "version": "deepseek/deepseek-chat",
        "context_window": 1_000_000,
        "input_cost_per_1m": "0.3000",
        "output_cost_per_1m": "1.2000",
        "capabilities": ["function_calling"],
        "superseded_by": "deepseek-flash",
        "deprecated": True,
    },
    {
        "model_id": "deepseek-reasoner",
        "display_name": "DeepSeek Reasoner (legacy)",
        "description": "Legacy reasoning alias — prefer deepseek-flash thinking mode or V4 Pro.",
        "tier": "brain",
        "version": "deepseek/deepseek-reasoner",
        "context_window": 1_000_000,
        "input_cost_per_1m": "1.3200",
        "output_cost_per_1m": "3.9600",
        "capabilities": ["function_calling", "reasoning"],
        "superseded_by": "deepseek-v4-pro",
        "deprecated": True,
    },
]


def seed_deepseek(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    for row in DEEPSEEK_ROWS:
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
    for row in DEEPSEEK_ROWS:
        if not row["superseded_by"]:
            continue
        replacement = ModelCatalog.objects.filter(model_id=row["superseded_by"]).first()
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


def unseed_deepseek(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    ModelCatalog.objects.filter(
        model_id__in=[r["model_id"] for r in DEEPSEEK_ROWS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0042_pulseheartbeat"),
    ]

    operations = [
        migrations.RunPython(seed_deepseek, unseed_deepseek),
    ]
