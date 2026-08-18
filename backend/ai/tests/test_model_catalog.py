"""Phase 20-A — Model catalog v2 tests.

Covers:

* three tiers present (≥2 fast / ≥2 balanced / ≥2 brain)
* the endpoint returns a backward-compatible superset shape
* deprecated rows are still returned
* cost fields are numeric
* exactly one model is flagged default (the configured default)
* superseded_by retirement links resolve
* the data-migration seed populates the catalog correctly
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.models import ModelCatalog


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="catalog-worker", password="secret123")


def _create_model(**overrides) -> ModelCatalog:
    base = {
        "model_id": "m-default",
        "display_name": "Default Model",
        "description": "A test model.",
        "tier": "balanced",
        "version": "openai/m-default",
        "context_window": 128000,
        "input_cost_per_1m": "2.50",
        "output_cost_per_1m": "10.00",
        "deprecated": False,
        "capabilities": ["vision", "function_calling"],
    }
    base.update(overrides)
    return ModelCatalog.objects.create(**base)


@pytest.fixture
def catalog_seed(db):
    """Seed a representative catalog mirroring the data-migration seed."""
    ModelCatalog.objects.all().delete()
    fast1 = _create_model(
        model_id="gpt-4o-mini", display_name="GPT-4o mini", tier="fast",
        version="openai/gpt-4o-mini",
        input_cost_per_1m="0.15", output_cost_per_1m="0.60",
    )
    fast2 = _create_model(
        model_id="claude-haiku-4.5", display_name="Claude Haiku 4.5", tier="fast",
        version="anthropic/claude-haiku-4.5",
        input_cost_per_1m="1.00", output_cost_per_1m="5.00",
    )
    bal = _create_model(
        model_id="claude-sonnet-4.5", display_name="Claude Sonnet 4.5", tier="balanced",
        version="anthropic/claude-sonnet-4.5",
        input_cost_per_1m="3.00", output_cost_per_1m="5.00",
    )
    brain = _create_model(
        model_id="gpt-4o", display_name="GPT-4o", tier="brain",
        version="openai/gpt-4o",
        input_cost_per_1m="2.50", output_cost_per_1m="10.00",
    )
    deprecated = _create_model(
        model_id="claude-3-5-sonnet", display_name="Claude 3.5 Sonnet", tier="balanced",
        version="anthropic/claude-3-5-sonnet-latest",
        input_cost_per_1m="3.00", output_cost_per_1m="15.00",
        deprecated=True, superseded_by=bal,
    )
    return [fast1, fast2, bal, brain, deprecated]


LEGACY_KEYS = {"id", "label", "description", "input_cost_per_1m", "output_cost_per_1m", "is_default"}
SUPERSET_KEYS = {"display_name", "tier", "version", "context_window", "deprecated", "superseded_by", "capabilities"}


@pytest.mark.django_db
def test_models_endpoint_superset_shape(user, catalog_seed):
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(reverse("ai-workspace-models"))
    assert resp.status_code == 200
    models = resp.data["models"]
    assert len(models) == 5

    for m in models:
        assert LEGACY_KEYS <= set(m.keys())
        assert SUPERSET_KEYS <= set(m.keys())
        assert isinstance(m["input_cost_per_1m"], (int, float))
        assert isinstance(m["output_cost_per_1m"], (int, float))
        assert isinstance(m["context_window"], int)
        assert m["tier"] in {"fast", "balanced", "brain"}


@pytest.mark.django_db
def test_models_endpoint_returns_deprecated(user, catalog_seed):
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(reverse("ai-workspace-models"))
    models = resp.data["models"]

    deprecated = [m for m in models if m["deprecated"]]
    assert len(deprecated) == 1
    assert deprecated[0]["id"] == "claude-3-5-sonnet"
    assert deprecated[0]["superseded_by"] == "claude-sonnet-4.5"


@pytest.mark.django_db
def test_models_endpoint_single_default(user, catalog_seed):
    from ai.engine.llm.router import get_model_for_task

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(reverse("ai-workspace-models"))
    models = resp.data["models"]

    defaults = [m for m in models if m["is_default"]]
    assert len(defaults) == 1

    expected = (get_model_for_task("chat") or "").strip().lower().rsplit("/", 1)[-1]
    d = defaults[0]
    assert expected in {d["id"].lower(), d["version"].rsplit("/", 1)[-1].lower()}


@pytest.mark.django_db
def test_models_endpoint_requires_auth(catalog_seed):
    client = APIClient()
    resp = client.get(reverse("ai-workspace-models"))
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_data_migration_seed_populates_catalog(db):
    """Exercise the data migration's seed/unseed against the live model."""
    import importlib

    mig = importlib.import_module("ai.migrations.0014_seed_model_catalog")
    seed_catalog = mig.seed_catalog
    unseed_catalog = mig.unseed_catalog

    class _FakeApps:
        def get_model(self, app_label, model_name):
            assert (app_label, model_name) == ("ai", "ModelCatalog")
            return ModelCatalog

    ModelCatalog.objects.all().delete()
    seed_catalog(_FakeApps(), None)

    assert ModelCatalog.objects.count() == 8
    assert ModelCatalog.objects.filter(tier="fast").count() >= 2
    assert ModelCatalog.objects.filter(tier="balanced").count() >= 2
    assert ModelCatalog.objects.filter(tier="brain").count() >= 2

    # Retirement path: deprecated rows link to their replacement.
    sonnet_35 = ModelCatalog.objects.get(model_id="claude-3-5-sonnet")
    assert sonnet_35.deprecated is True
    assert sonnet_35.superseded_by.model_id == "claude-sonnet-4.5"

    haiku_35 = ModelCatalog.objects.get(model_id="claude-haiku-3.5")
    assert haiku_35.deprecated is True
    assert haiku_35.superseded_by.model_id == "claude-haiku-4.5"

    unseed_catalog(_FakeApps(), None)
    assert ModelCatalog.objects.count() == 0
