"""
User-scoped access manifest for the AI assistant (capability-scoped listing).

UX/security audit requirement — the assistant's "what can you do" listing must
be grounded in the *user's actual access*, never in a static or global
inventory:

  * The assistant may mention ONLY what this manifest contains: apps, work
    areas, modules, capabilities the user can actually reach.  Anything absent
    here must stay absent from the assistant's replies — even its existence
    must not leak.
  * The platform name comes from Django settings (``PLATFORM_NAME`` /
    ``PLATFORM_TITLE``), never hardcoded.
  * No component/technology/stack/AI-internals are ever included here.  This
    is the user-facing inventory, written in user-facing language (RULE_23).

This module is host-side glue (like ``ai.host_executor``): it reads Django
ORM models to build the per-user inventory consumed by the engine's system
prompt (``instance_config["user_access"]``) and by the ``list_my_capabilities``
plugin.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("carbon.ai.access_manifest")

#: Work areas presented to the assistant, each gated on at least one real
#: capability key (keys are existence-checked against ALL_CAPABILITIES, so a
#: stale key silently excludes, never leaks).  ``route`` may be ``None`` — the
#: assistant then mentions the area without a page link.
_WORK_AREAS: list[dict[str, Any]] = [
    {
        "key": "carbon",
        "label": "Emissions & Carbon Data",
        "description": "View emissions data, dashboards and carbon calculations.",
        "route": "/carbon/dashboard",
        "capabilities": [
            "carbon:view_dashboard", "carbon:view_console", "carbon:view_calculations",
        ],
    },
    {
        "key": "carbon.analytics",
        "label": "Data Analysis & Reporting",
        "description": "Analyze data and generate reports.",
        "route": "/carbon/analytics",
        "capabilities": ["carbon:view_analytics", "carbon:generate_reports"],
    },
    {
        "key": "dq",
        "label": "Data Quality",
        "description": "Inspect, test and manage data quality rules and their results.",
        "route": "/dq",
        "capabilities": ["dq:view", "dq:manage_rules"],
    },
    {
        "key": "catalog",
        "label": "Data Catalog & Governance",
        "description": "Discover data products, schemas, policies and governance assets.",
        "route": "/catalog",
        "capabilities": [
            "catalog:view", "catalog:manage_products", "catalog:manage_metadata",
            "catalog:manage_policies", "catalog:view_governance",
        ],
    },
    {
        "key": "mdm",
        "label": "Master Data",
        "description": "Browse and manage reference data sets.",
        "route": "/catalog/mdm",
        "capabilities": ["mdm:view", "mdm:manage"],
    },
    {
        "key": "connections",
        "label": "Data Connections",
        "description": "Manage data source connections.",
        "route": "/catalog/connections",
        "capabilities": ["connections:view", "connections:manage"],
    },
    {
        "key": "importexport",
        "label": "Import & Export",
        "description": "Import and export data packages.",
        "route": "/catalog/importexport",
        "capabilities": ["importexport:view", "importexport:manage"],
    },
    {
        "key": "dataschema",
        "label": "Data Schema",
        "description": "Browse schemas and data dictionaries.",
        "route": "/catalog",
        "capabilities": ["dataschema:view", "dataschema:manage"],
    },
    {
        "key": "evidence",
        "label": "Evidence & Assurance",
        "description": "View evidence records supporting data quality and carbon data.",
        "route": None,
        "capabilities": ["evidence:view", "evidence:manage"],
    },
    {
        "key": "datahub",
        "label": "Data Hub",
        "description": "Ingest and manage datasets in the data hub.",
        "route": None,
        "capabilities": ["datahub:view", "datahub:ingest", "datahub:approve", "datahub:manage"],
    },
    {
        "key": "ai",
        "label": "AI Workspace",
        "description": "Use the AI workspace for assisted analysis.",
        "route": "/carbon/console",
        "capabilities": ["ai:view_console", "ai:manage_console"],
    },
    {
        "key": "turnkey",
        "label": "TurnKey",
        "description": "Work with TurnKey-integrated datasets.",
        "route": None,
        "capabilities": ["turnkey:view", "turnkey:manage"],
    },
    {
        "key": "appregistry",
        "label": "Platform Apps",
        "description": "Manage platform apps and their activation.",
        "route": None,
        "capabilities": ["appregistry:view", "appregistry:manage"],
    },
    {
        "key": "platform",
        "label": "Platform Administration",
        "description": "Manage users, groups, org units and access control.",
        "route": None,
        "capabilities": [
            "platform:admin", "platform:manage_users", "platform:manage_groups",
            "platform:manage_org_units", "platform:manage_access",
            "platform:view_audit", "platform:manage_apps",
        ],
    },
]

#: Capability keys that imply the user can *operate* (not just view) in a work
#: area.  Used for the "view-only vs view-and-operate" access level.
_OPERATE_CAPABILITIES: frozenset[str] = frozenset({
    "dq:manage_rules",
    "catalog:manage_products", "catalog:manage_metadata", "catalog:manage_policies",
    "mdm:manage", "connections:manage", "importexport:manage",
    "dataschema:manage", "evidence:manage", "datahub:ingest", "datahub:approve",
    "datahub:manage", "ai:manage_console", "turnkey:manage", "appregistry:manage",
    "carbon:enter_data", "carbon:manage_emission_factors", "carbon:manage_calculation_rules",
    "carbon:manage_gwp", "carbon:manage_sbti_targets", "carbon:manage_reporting_periods",
    "carbon:trigger_calculations", "carbon:verify_data", "carbon:generate_reports",
    "platform:admin", "platform:manage_users", "platform:manage_groups",
    "platform:manage_org_units", "platform:manage_access", "platform:manage_apps",
})

#: Fallback frontend route for apps that declare no ``entry_route``.  Unknown
#: slugs get no route — never guess a page that may not exist.
_APP_ROUTE_FALLBACK: dict[str, str] = {
    "carbon": "/carbon/console",
    "dq": "/dq",
    "catalog": "/catalog",
    "mdm": "/catalog/mdm",
    "emissions": "/carbon/dashboard",
    "connections": "/catalog/connections",
    "importexport": "/catalog/importexport",
    "governance": "/catalog/governance",
}

#: Cap on navigation links emitted to the UI per listing.
_MAX_ROUTES = 8


def _platform_name() -> str:
    """Config-driven platform name (never hardcoded)."""
    from django.conf import settings as dj_settings

    title = getattr(dj_settings, "PLATFORM_TITLE", "") or ""
    name = getattr(dj_settings, "PLATFORM_NAME", "") or ""
    return title or name or "Data Trust Platform"


def _user_capability_keys(user) -> frozenset[str]:
    from accounts.capabilities import get_user_capabilities

    return get_user_capabilities(user)


def _is_operate(user, caps: frozenset[str]) -> bool:
    if "*" in caps:
        return True
    return bool(caps & _OPERATE_CAPABILITIES)


def _work_areas_for(caps: frozenset[str]) -> list[dict[str, str]]:
    """Work areas the user can reach (user-facing labels only)."""
    from accounts.capabilities import ALL_CAPABILITIES

    if "*" in caps:
        return [
            {"key": wa["key"], "label": wa["label"], "description": wa["description"],
             "route": wa.get("route")}
            for wa in _WORK_AREAS
        ]
    result: list[dict[str, str]] = []
    for wa in _WORK_AREAS:
        required = [k for k in wa["capabilities"] if k in ALL_CAPABILITIES]
        if required and caps.intersection(required):
            result.append({
                "key": wa["key"], "label": wa["label"], "description": wa["description"],
                "route": wa.get("route"),
            })
    return result


def _apps_for(scope) -> list[dict[str, str]]:
    """Activated + capability-gated apps the user can reach (App Registry §7.5).

    Only apps in ``scope.active_apps`` (already activation- and capability-
    gated by ``build_scope``) are ever listed — the existence of any other app
    is not exposed.
    """
    from appregistry.models import AppManifest

    active = scope.active_apps or []
    if not active:
        return []
    rows = AppManifest.objects.filter(slug__in=active).only(
        "slug", "name", "description", "entry_route"
    )
    apps: list[dict[str, str]] = []
    for row in rows:
        route = (row.entry_route or "").strip() or _APP_ROUTE_FALLBACK.get(row.slug) or ""
        description = (row.description or "").strip() or f"{row.name} workspace."
        apps.append({
            "key": row.slug,
            "name": row.name,
            "description": description,
            "route": route,
        })
    return apps


def _modules_for(scope) -> list[dict[str, str]]:
    """Modules (org-scoped data areas) the user can reach.

    Superusers see everything via ``["*"]``; enumerating every module for them
    would flood the prompt, so platform-wide users get an empty list and rely
    on the ``platform_wide`` flag instead.
    """
    from core.models import Module

    module_ids = scope.module_ids or []
    if not module_ids or getattr(scope, "is_superuser", False):
        return []
    rows = Module.objects.filter(id__in=module_ids).only("id", "name")
    return [
        {"key": str(row.id), "name": row.name, "route": f"/catalog/products/{row.id}"}
        for row in rows
    ]


def build_user_access_manifest(host_user_id: str | int | None) -> dict[str, Any]:
    """Build the capability-scoped inventory for ``host_user_id``.

    Returns a dict consumed by:
      * the engine system prompt (``[Your Access]`` section), and
      * the ``list_my_capabilities`` plugin (machine-readable page links).

    Unknown/missing users return a minimal manifest (empty inventory) — the
    assistant may then only give generic, non-inventory answers.
    """
    if not host_user_id:
        return _minimal_manifest()

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=host_user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        logger.warning("build_user_access_manifest: user %r not found", host_user_id)
        return _minimal_manifest()

    from ai.intelligence import build_scope

    scope = build_scope(user)
    caps = _user_capability_keys(user)
    platform_wide = bool(getattr(scope, "is_superuser", False)) or "*" in caps

    work_areas = _work_areas_for(caps)
    apps = _apps_for(scope)
    modules = _modules_for(scope)

    # ── Deduplicated, capped navigation links ────────────────────────────
    routes: list[dict[str, str]] = []
    seen: set[str] = set()

    def _push_route(route: str, label: str, summary: str) -> None:
        route = (route or "").strip()
        if not route or route in seen:
            return
        seen.add(route)
        routes.append({"route": route, "label": label, "summary": summary})

    for wa in work_areas:
        if wa.get("route"):
            _push_route(wa["route"], wa["label"], wa["description"])
    for app in apps:
        if app.get("route"):
            _push_route(app["route"], app["name"], app["description"])
    for module in modules:
        if module.get("route"):
            _push_route(module["route"], module["name"], f"Data area: {module['name']}")
    routes = routes[:_MAX_ROUTES]

    if platform_wide:
        access_level = "platform-wide (all data areas and apps)"
    elif _is_operate(user, caps):
        access_level = "view and operate"
    else:
        access_level = "view-only"

    return {
        "platform_name": _platform_name(),
        "access_level": access_level,
        "platform_wide": platform_wide,
        "is_read_only": bool(getattr(scope, "is_read_only", True)),
        "apps": apps,
        "capabilities": work_areas,
        "modules": modules,
        "routes": routes,
    }


def _minimal_manifest() -> dict[str, Any]:
    """Empty inventory — nothing may be listed, existence must not leak."""
    return {
        "platform_name": _platform_name(),
        "access_level": "unknown",
        "platform_wide": False,
        "is_read_only": True,
        "apps": [],
        "capabilities": [],
        "modules": [],
        "routes": [],
    }
