"""Pulse 0.3 — Phase E1: Host Adapter (WorldModel + ToolCatalog) seam tests.

Proves:
  * ``ai.adapter.types`` imports with zero Django imports (no settings needed).
  * ``CarbonHostAdapter`` constructs and is a ``HostAdapterContract``.
  * the adapter seam is injectable: ``assemble_context`` / T3 / T4 logic is
    testable with a mock adapter and no live ORM.
  * the world model is registry-driven (never a hardcoded list).
  * ``get_tool_catalog`` is functional (never ``NotImplementedError``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mdm.models import OrgUnit

from ai.adapter import HostAdapterContract, ToolCatalog, WorldModel
from ai.adapter.carbon import CarbonHostAdapter
from ai.context_assembler import assemble_context


# ── (a) ai.adapter.types is Django-free ─────────────────────────────────


def test_adapter_types_import_without_django():
    """``ai.adapter.types`` must import with zero Django imports.

    Uses a fresh subprocess with ``DJANGO_SETTINGS_MODULE`` removed so we
    prove the module never touches Django (not just that it happens to work
    after settings are configured).
    """
    backend_dir = Path(__file__).resolve().parents[2]
    code = (
        "import sys;"
        "import ai.adapter.types as t;"
        "import ai.adapter as a;"
        "assert 'django' not in sys.modules, 'django imported by adapter';"
        "assert hasattr(t, 'WorldModel');"
        "assert hasattr(t, 'ToolCatalog');"
        "assert hasattr(a, 'HostAdapterContract');"
        "print('types-OK')"
    )
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "types-OK" in proc.stdout


# ── (b) CarbonHostAdapter constructs ────────────────────────────────────


def test_carbon_host_adapter_is_a_host_adapter():
    adapter = CarbonHostAdapter()
    assert isinstance(adapter, HostAdapterContract)


@pytest.mark.django_db
def test_get_world_model_is_registry_driven():
    adapter = CarbonHostAdapter()
    wm = adapter.get_world_model()
    assert isinstance(wm, WorldModel)
    assert isinstance(wm.domains, list)
    assert isinstance(wm.entities, list)
    # "emissions" is registered by ai.apps.ready() -> register_builtin_domains.
    assert "emissions" in wm.domains


@pytest.mark.django_db
def test_resolve_mentions_org_unit():
    adapter = CarbonHostAdapter()
    ou = OrgUnit.objects.create(name="Engineering", org_type="department")

    resolved = adapter.resolve_mentions([{"kind": "org-unit", "id": ou.id}])
    assert resolved == [
        {
            "kind": "org-unit",
            "id": str(ou.id),
            "name": ou.name,
            "org_type": ou.org_type,
        }
    ]

    # alias kind resolves identically
    assert adapter.resolve_mentions([{"kind": "orgunit", "id": ou.id}]) == resolved

    # unknown id / unknown kind resolve to nothing
    assert adapter.resolve_mentions([{"kind": "org-unit", "id": 999999}]) == []
    assert adapter.resolve_mentions([{"kind": "bogus", "id": ou.id}]) == []


@pytest.mark.django_db
def test_get_tool_catalog_is_functional():
    adapter = CarbonHostAdapter()
    catalog = adapter.get_tool_catalog(user=None, scope=None)
    assert isinstance(catalog, ToolCatalog)
    # The chat spine is frozen; the catalog must expose at least one tool.
    assert len(catalog.tools) >= 1
    ids = {tool.id for tool in catalog.tools}
    assert "search_knowledge" in ids


# ── (c) the adapter seam is injectable / mockable ───────────────────────


class _StubAdapter:
    """Minimal HostAdapterContract stand-in: records calls, touches no ORM."""

    def __init__(self):
        self.calls: list[str] = []

    def build_user_profile(self, scope, user):
        self.calls.append("build_user_profile")
        return {
            "role": "system",
            "content": "[User Profile]\nname=stub",
            "timestamp": None,
        }

    def user_memory_enabled(self, conversation):
        self.calls.append("user_memory_enabled")
        return True

    def retrieve_long_term_memory(self, scope, memory_budget):
        self.calls.append("retrieve_long_term_memory")
        return (
            [{"category": "pref", "content": "likes dark mode", "confidence": 0.9, "source": "stub"}],
            10,
        )

    def retrieve_knowledge_graph(self, scope, retrieval_budget):
        self.calls.append("retrieve_knowledge_graph")
        return (
            [{"name": "emission_factors", "node_type": "ENTITY", "confidence": 1.0, "attributes": ["factor"]}],
            20,
        )

    def resolve_mentions(self, mentions):
        self.calls.append("resolve_mentions")
        return []

    # contract methods (not used by assemble_context; present for completeness)
    def get_world_model(self):
        return WorldModel()

    def get_tool_catalog(self, user, scope):
        return ToolCatalog()

    def assemble_context(self, query, user, scope, page_context):
        raise NotImplementedError

    def get_org_memory_seeds(self, instance_id):
        return []


def test_assemble_context_uses_injected_adapter_without_orm():
    adapter = _StubAdapter()
    conversation = SimpleNamespace(user=None, summary="sum", task_payload_json={})
    messages = [
        {"id": "m1", "role": "user", "content": "hi", "created_at": None, "is_deleted": False}
    ]

    result = assemble_context(conversation, messages, scope=None, adapter=adapter)

    # The injected adapter's T3/T4/profile/memory methods were all exercised.
    assert "build_user_profile" in adapter.calls
    assert "user_memory_enabled" in adapter.calls
    assert "retrieve_long_term_memory" in adapter.calls
    assert "retrieve_knowledge_graph" in adapter.calls

    contents = " | ".join(m["content"] for m in result["messages"])
    assert "likes dark mode" in contents          # T4 memory injected
    assert "emission_factors" in contents         # T3 KG injected
    assert result["budget"]["T3_retrieval"] == 20
    assert result["budget"]["T4_memory"] == 10
    assert result["kg_entities"][0]["name"] == "emission_factors"
