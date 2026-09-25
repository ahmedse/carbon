"""Seed cheap Poe models into the Pulse picker catalog.

Haiku 4.5, GPT-4o mini, and DeepSeek Flash are already seeded. These are the
other low-cost Poe bots with tool calling: GPT-4.1 mini and the Gemini Flash
family. Rates are published list prices so usage never under-counts.
"""

from django.db import migrations


CHEAP_POE_ROWS = [
    {
        "model_id": "gpt-4.1-mini",
        "display_name": "GPT-4.1 mini",
        "description": "Cheap OpenAI mini on Poe. Tool calling. Far under GPT-4o.",
        "tier": "fast",
        "version": "openai/gpt-4.1-mini",
        "context_window": 1_047_576,
        "input_cost_per_1m": "0.4000",
        "output_cost_per_1m": "1.6000",
        "capabilities": ["vision", "function_calling"],
    },
    {
        "model_id": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "description": "Cheap Google Flash on Poe. Tool calling. Under Haiku on output.",
        "tier": "fast",
        "version": "google/gemini-2.5-flash",
        "context_window": 1_048_576,
        "input_cost_per_1m": "0.3000",
        "output_cost_per_1m": "2.5000",
        "capabilities": ["vision", "function_calling"],
    },
    {
        "model_id": "gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash-Lite",
        "description": "Cheapest Gemini on Poe. Tool calling. Routine turns.",
        "tier": "fast",
        "version": "google/gemini-2.5-flash-lite",
        "context_window": 1_048_576,
        "input_cost_per_1m": "0.1000",
        "output_cost_per_1m": "0.4000",
        "capabilities": ["vision", "function_calling"],
    },
    {
        "model_id": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "description": "Cheap Gemini Flash on Poe. Tool calling.",
        "tier": "fast",
        "version": "google/gemini-2.0-flash",
        "context_window": 1_048_576,
        "input_cost_per_1m": "0.1000",
        "output_cost_per_1m": "0.4000",
        "capabilities": ["vision", "function_calling"],
    },
]


def seed_cheap_poe(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    for row in CHEAP_POE_ROWS:
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


def unseed_cheap_poe(apps, schema_editor):
    ModelCatalog = apps.get_model("ai", "ModelCatalog")
    ModelCatalog.objects.filter(
        model_id__in=[r["model_id"] for r in CHEAP_POE_ROWS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0045_pulsecontrolstate"),
    ]

    operations = [
        migrations.RunPython(seed_cheap_poe, unseed_cheap_poe),
    ]
