"""
UX/security audit — capability-scoped assistant inventory tests.

Covers ``ai.access_manifest.build_user_access_manifest`` (the per-user
inventory that grounds the assistant's "what can you do" listing) and the
runtime's multi-link action extraction for the ``list_my_capabilities`` tool.

No-leak contract under test:
  * only the user's actual access appears (apps gated by activation +
    capability, work areas by capability, modules by org scope);
  * the platform name comes from settings, never hardcoded;
  * unknown/anonymous users get an EMPTY inventory — nothing to leak.
"""
import pytest

from django.conf import settings

from ai.access_manifest import build_user_access_manifest
from ai.engine_runtime import _extract_tool_actions, _grounded_access_table
from ai.engine.agent.plugins import registered_plugins


# ── Manifest scoping ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAccessManifestScoping:
    def test_dq_user_sees_only_dq(self, create_user, create_scoped_role):
        user = create_user("dq_only_user")
        create_scoped_role(user, "dq_lead")
        manifest = build_user_access_manifest(user.pk)

        labels = {wa["label"] for wa in manifest["capabilities"]}
        assert "Data Quality" in labels
        # Existence of other domains must NOT leak.
        assert "Data Catalog & Governance" not in labels
        assert "Emissions & Carbon Data" not in labels
        assert "Platform Administration" not in labels

        routes = {r["route"] for r in manifest["routes"]}
        assert "/dq" in routes
        assert "/catalog" not in routes
        assert "/carbon/dashboard" not in routes

    def test_catalog_user_sees_only_catalog(self, create_user, create_scoped_role):
        user = create_user("catalog_only_user")
        create_scoped_role(user, "catalog_lead")
        manifest = build_user_access_manifest(user.pk)

        labels = {wa["label"] for wa in manifest["capabilities"]}
        assert "Data Catalog & Governance" in labels
        assert "Data Quality" not in labels

    def test_viewer_is_read_only(self, create_user, create_scoped_role):
        user = create_user("readonly_user")
        create_scoped_role(user, "viewers_group")
        manifest = build_user_access_manifest(user.pk)

        assert manifest["is_read_only"] is True
        assert manifest["access_level"] == "view-only"

    def test_superuser_is_platform_wide(self, create_user):
        user = create_user("root_user", is_superuser=True)
        manifest = build_user_access_manifest(user.pk)

        assert manifest["platform_wide"] is True
        labels = {wa["label"] for wa in manifest["capabilities"]}
        assert "Data Quality" in labels
        assert "Platform Administration" in labels
        assert "Emissions & Carbon Data" in labels

    def test_platform_name_is_config_driven(self, create_user, create_scoped_role):
        user = create_user("name_probe")
        create_scoped_role(user, "dq_lead")
        manifest = build_user_access_manifest(user.pk)

        expected = (
            getattr(settings, "PLATFORM_TITLE", "")
            or getattr(settings, "PLATFORM_NAME", "")
            or "Data Trust Platform"
        )
        assert manifest["platform_name"] == expected
        assert manifest["platform_name"] != "Carbon Data Trust Platform"

    def test_module_scope_included_for_regular_user(self, create_user, create_scoped_role):
        from core.models import Module

        module = Module.objects.create(name="Scoped Manifest Module")
        user = create_user("module_user")
        create_scoped_role(user, "dq_lead", module=module)
        manifest = build_user_access_manifest(user.pk)

        assert any(m["key"] == str(module.pk) for m in manifest["modules"])
        assert any(m["name"] == "Scoped Manifest Module" for m in manifest["modules"])

    def test_unknown_user_gets_empty_inventory(self):
        manifest = build_user_access_manifest(999_999_999)
        assert manifest["apps"] == []
        assert manifest["capabilities"] == []
        assert manifest["modules"] == []
        assert manifest["routes"] == []
        assert manifest["access_level"] == "unknown"

    def test_none_host_user_gets_empty_inventory(self):
        manifest = build_user_access_manifest(None)
        assert manifest["apps"] == []
        assert manifest["capabilities"] == []
        assert manifest["routes"] == []


@pytest.mark.django_db
class TestAppGating:
    def _make_app(self, slug, name, required_capabilities=None):
        from appregistry.models import AppActivation, AppManifest

        app = AppManifest.objects.create(
            slug=slug, name=name, version="1.0.0",
            required_capabilities=required_capabilities or [],
        )
        AppActivation.objects.get_or_create(app=app)
        return app

    def test_apps_are_activation_and_capability_gated(self, create_user, create_scoped_role):
        # healthy: no capability gate → any authenticated user. water: gated.
        self._make_app(slug="healthy", name="Healthy Foods", required_capabilities=[])
        self._make_app(
            slug="water", name="Water Quality",
            required_capabilities=["carbon:view_dashboard"],
        )

        dq_user = create_user("dq_user")
        create_scoped_role(dq_user, "dq_lead")
        dq_manifest = build_user_access_manifest(dq_user.pk)
        dq_apps = {a["key"] for a in dq_manifest["apps"]}
        assert "healthy" in dq_apps          # ungated → reachable
        assert "water" not in dq_apps        # gated → must not leak

        carbon_user = create_user("carbon_user")
        create_scoped_role(carbon_user, "viewers_group")  # carbon:view_dashboard
        carbon_manifest = build_user_access_manifest(carbon_user.pk)
        carbon_apps = {a["key"] for a in carbon_manifest["apps"]}
        assert "water" in carbon_apps

    def test_inactive_app_never_appears(self, create_user, create_scoped_role):
        from appregistry.models import AppActivation

        self._make_app(slug="healthy", name="Healthy Foods", required_capabilities=[])
        AppActivation.objects.update(is_active=False)

        user = create_user("user")
        create_scoped_role(user, "dq_lead")
        manifest = build_user_access_manifest(user.pk)
        assert manifest["apps"] == []


# ── Runtime multi-link actions (list_my_capabilities) ──────────────────────


class TestRoutesActionExtraction:
    def test_routes_list_emits_navigate_actions(self):
        completed_tools = [
            {
                "tool_name": "list_my_capabilities",
                "result": {
                    "requires_confirmation": False,
                    "action": "list_capabilities",
                    "routes": [
                        {"route": "/dq", "label": "Data Quality",
                         "summary": "Inspect, test and manage data quality rules."},
                        {"route": "/catalog", "label": "Data Catalog & Governance",
                         "summary": "Discover data products and governance assets."},
                    ],
                },
            }
        ]
        actions, pending = _extract_tool_actions(completed_tools)
        assert pending == []
        assert [a["route"] for a in actions] == ["/dq", "/catalog"]
        assert actions[0]["type"] == "navigate"
        assert actions[0]["label"] == "Data Quality"

    def test_routes_list_deduped(self):
        completed_tools = [
            {
                "tool_name": "list_my_capabilities",
                "result": {
                    "routes": [
                        {"route": "/dq", "label": "Data Quality", "summary": "a"},
                        {"route": "/dq", "label": "Data Quality", "summary": "b"},
                    ],
                },
            },
            {
                "tool_name": "other",
                "result": {"action": "navigate", "route": "/dq", "label": "Open"},
            },
        ]
        actions, _ = _extract_tool_actions(completed_tools)
        assert len(actions) == 1
        assert actions[0]["route"] == "/dq"

    def test_plugin_registered(self):
        names = {p.name for p in registered_plugins()}
        assert "list_my_capabilities" in names

    def test_plugin_definition_available_to_agent(self):
        from ai.engine.agent.tools import get_tool_definitions

        defs = get_tool_definitions()
        names = {d.get("function", {}).get("name") for d in defs}
        assert "list_my_capabilities" in names


# ── Unified rich "Your Access" document (deterministic GFM table) ──────────


class TestGroundedAccessTable:
    def _tool(self, result):
        return {"tool_name": "list_my_capabilities", "result": result}

    def test_empty_when_tool_did_not_run(self):
        assert _grounded_access_table([]) == ""

    def test_empty_when_other_tool_ran(self):
        tools = [{"tool_name": "create_dq_rule", "result": {"requires_confirmation": True}}]
        assert _grounded_access_table(tools) == ""

    def test_rich_table_with_work_areas_apps_modules(self):
        result = {
            "action": "list_capabilities",
            "capabilities": [
                {"key": "dq", "label": "Data Quality",
                 "description": "Inspect, test and manage data quality rules.",
                 "route": "/dq"},
                {"key": "catalog", "label": "Data Catalog & Governance",
                 "description": "Discover data products.",
                 "route": "/catalog"},
            ],
            "apps": [
                {"key": "healthy", "name": "Healthy Foods",
                 "description": "Food safety app", "route": "/carbon/dashboard"},
            ],
            "modules": [
                {"key": "10", "name": "ALM", "route": "/catalog/products/10"},
            ],
            "routes": [],
        }
        doc = _grounded_access_table([self._tool(result)])
        assert doc.startswith("## Your Access")
        assert "### Work areas" in doc
        assert "| Work area | Description | Open |" in doc
        assert "| Data Quality | Inspect, test and manage data quality rules. | [Open](/dq) |" in doc
        assert "| Data Catalog & Governance | Discover data products. | [Open](/catalog) |" in doc
        assert "### Apps you can open" in doc
        assert "| Healthy Foods | Food safety app | [Open](/carbon/dashboard) |" in doc
        assert "### Data areas (modules)" in doc
        assert "| ALM | [Open](/catalog/products/10) |" in doc

    def test_escapes_pipes_in_cells(self):
        result = {
            "action": "list_capabilities",
            "capabilities": [
                {"key": "x", "label": "A | B", "description": "pipe | in text", "route": "/x"},
            ],
            "apps": [], "modules": [], "routes": [],
        }
        doc = _grounded_access_table([self._tool(result)])
        assert "| A \\| B | pipe \\| in text | [Open](/x) |" in doc

    def test_drops_items_without_route(self):
        result = {
            "action": "list_capabilities",
            "capabilities": [
                {"key": "no-route", "label": "Hidden", "description": "No page.", "route": ""},
                {"key": "dq", "label": "Data Quality", "description": "Has page.", "route": "/dq"},
            ],
            "apps": [], "modules": [], "routes": [],
        }
        doc = _grounded_access_table([self._tool(result)])
        assert "Hidden" not in doc
        assert "Data Quality" in doc

    def test_empty_when_inventory_empty(self):
        result = {
            "action": "list_capabilities",
            "capabilities": [], "apps": [], "modules": [], "routes": [],
        }
        assert _grounded_access_table([self._tool(result)]) == ""
